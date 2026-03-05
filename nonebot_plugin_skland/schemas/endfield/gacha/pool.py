"""终末地卡池相关模型"""

from typing import Any

from pydantic import BaseModel
from nonebot.compat import model_validator

from .base import EfGachaPull, EfGachaGroup

# 角色池武库配额产出规则：rarity 在 API 中是 0-indexed (3=4★, 4=5★, 5=6★)
ARSENAL_QUOTA_EARN_MAP: dict[int, int] = {
    4: 20,  # 4★ → 产出 20 配额
    5: 200,  # 5★ → 产出 200 配额
    6: 2000,  # 6★ → 产出 2000 配额
}

# 武器池每次十连消耗的武库配额
WEAPON_TEN_PULL_COST: int = 1980


class EfGachaPoolInfo(BaseModel):
    """终末地卡池信息"""

    pool_id: str
    pool_name: str
    pool_type: str
    """物品类型: 'char' 或 'weapon'"""
    records: list[EfGachaGroup]
    """该卡池的抽卡记录分组（按时间倒序）"""
    up_six_chars: list[str] = []
    """UP六星角色/武器列表（仅up6_name对应的角色ID）"""
    up6_img: str = ""
    """UP六星角色横幅图片URL（用于模板banner背景）"""
    up6_name: str = ""
    """UP六星角色名称（用于模板显示）"""

    @property
    def pool_category(self) -> str:
        """根据 pool_id 推导卡池类别

        - pool_id 以 'special' 开头 → 'special'
        - pool_id 以 'weapon' 开头 → 'weapon'
        - pool_id == 'standard' → 'standard'
        - pool_id == 'beginner' → 'beginner'
        """
        pid = self.pool_id.lower()
        if pid.startswith("special"):
            return "special"
        if pid.startswith("weapon") or pid.startswith("wepon"):
            return "weapon"
        if pid == "beginner":
            return "beginner"
        return "standard"

    @model_validator(mode="before")
    @classmethod
    def sort_records(cls, values) -> Any:
        if "records" in values:
            values["records"] = sorted(values["records"], key=lambda x: x.gacha_ts, reverse=True)
        return values

    @property
    def all_pulls_chronological(self) -> list[EfGachaPull]:
        """所有抽卡记录，按时间正序排列（seq_id 升序）"""
        pulls: list[EfGachaPull] = []
        for record in reversed(self.records):
            pulls.extend(reversed(record.pulls))
        return pulls

    @property
    def all_pulls_reverse_chronological(self) -> list[EfGachaPull]:
        """所有抽卡记录，按时间倒序排列（最新在前）"""
        pulls: list[EfGachaPull] = []
        for record in self.records:
            for pull in record.pulls:
                pulls.append(pull)
        return pulls

    @property
    def total_pulls(self) -> int:
        """该卡池的总抽卡次数"""
        return sum(len(record.pulls) for record in self.records)

    @property
    def paid_pulls(self) -> int:
        """该卡池的付费抽数（不含 isFree）"""
        return sum(1 for record in self.records for pull in record.pulls if not pull.is_free)

    @property
    def free_pulls(self) -> int:
        """该卡池的免费抽数（isFree=True）"""
        return sum(1 for record in self.records for pull in record.pulls if pull.is_free)

    @property
    def total_six_stars(self) -> int:
        """该卡池的总六星数"""
        return sum(1 for record in self.records for pull in record.pulls if pull.rarity == 6)

    @property
    def total_six_spook(self) -> int:
        """该卡池的总六星歪数（非UP六星）"""
        return sum(
            1
            for record in self.records
            for pull in record.pulls
            if pull.rarity == 6 and pull.item_id not in self.up_six_chars
        )

    # ── 武库配额 ──

    @property
    def arsenal_quota_earned(self) -> int:
        """该卡池产出的武库配额总数（角色池专用）

        根据每次非免费抽卡获得的物品稀有度计算产出。
        """
        return sum(ARSENAL_QUOTA_EARN_MAP.get(pull.rarity, 0) for record in self.records for pull in record.pulls)

    @property
    def ten_pull_count(self) -> int:
        """该卡池的十连次数（武器池专用）

        同一 gachaTs 内连续 seqId 的非免费抽卡视为同一次十连。
        """
        ten_pulls: set[tuple[int, int]] = set()
        for group in self.records:
            paid = [p for p in group.pulls if not p.is_free]
            if not paid:
                continue
            sorted_paid = sorted(paid, key=lambda p: p.seq_id)
            # 连续 seqId 分组
            current_start = sorted_paid[0].seq_id
            prev_seq = current_start
            for p in sorted_paid[1:]:
                if p.seq_id != prev_seq + 1:
                    # 新的一组十连
                    ten_pulls.add((group.gacha_ts, current_start))
                    current_start = p.seq_id
                prev_seq = p.seq_id
            ten_pulls.add((group.gacha_ts, current_start))
        return len(ten_pulls)

    @property
    def arsenal_quota_consumed(self) -> int:
        """该卡池消耗的武库配额总数（武器池专用）

        每次十连消耗 1980 武库配额。
        """
        return self.ten_pull_count * WEAPON_TEN_PULL_COST

    # ── 保底（排除 isFree） ──

    @property
    def pity_count(self) -> int:
        """该卡池当前已垫抽数（排除 isFree 抽）

        从最新记录往前数：
        - 跳过 isFree 的抽（不计入垫抽）
        - 遇到非免费的 6★ 停止（重置保底）
        - 免费的 6★ 不重置保底
        """
        count = 0
        for pull in self.all_pulls_reverse_chronological:
            if pull.is_free:
                continue
            if pull.rarity == 6:
                return count
            count += 1
        return count

    @property
    def up_pity_count(self) -> int:
        """该卡池距上次出UP六星后的非免费抽数（仅 SPECIAL 卡池有意义）

        从最新记录往前数，跳过 isFree，直到遇到非免费的 UP 6★。
        如果没有出过非免费的 UP 6★，则返回总付费抽数。
        """
        count = 0
        for pull in self.all_pulls_reverse_chronological:
            if pull.is_free:
                continue
            if pull.rarity == 6 and pull.item_id in self.up_six_chars:
                return count
            count += 1
        return count

    @property
    def has_pulled_up_six(self) -> bool:
        """是否已经在该卡池中抽到过UP六星（含免费抽）

        用于判断是否显示「已获得UP」。
        """
        if not self.up_six_chars:
            return False
        return any(
            pull.rarity == 6 and pull.item_id in self.up_six_chars for record in self.records for pull in record.pulls
        )
