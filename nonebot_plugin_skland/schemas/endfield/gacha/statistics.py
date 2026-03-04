"""终末地抽卡统计模型"""

from typing import Any

from pydantic import BaseModel
from nonebot.compat import model_validator

from .base import EfGachaPull
from .pool import EfGachaPoolInfo


class EfGroupedGachaRecord(BaseModel):
    """终末地分组后的抽卡记录

    卡池按 pool_id 推导分类：
    - beginner: 新手启程池（40抽限定，必出1个6★，保底独立）
    - standard: 常驻池（80抽小保底，保底独立）
    - special*: 限定UP池（80抽小保底跨池继承，每池120抽大保底必出UP6★）
    - weapon*: 武器池（各池独立保底，仅十连，每次消耗1980武库配额）

    isFree 的抽不计入保底计算（出6★也不重置保底）。
    """

    beginner_pools: list[EfGachaPoolInfo] = []
    """新手启程卡池"""
    standard_pools: list[EfGachaPoolInfo] = []
    """常驻角色池"""
    special_pools: list[EfGachaPoolInfo] = []
    """限定UP角色池"""
    weapon_pools: list[EfGachaPoolInfo] = []
    """武器池"""

    @model_validator(mode="before")
    @classmethod
    def sort_pools(cls, values) -> Any:
        if isinstance(values, dict):
            for key in ("beginner_pools", "standard_pools", "special_pools", "weapon_pools"):
                if key in values and values[key]:
                    values[key] = sorted(
                        values[key],
                        key=lambda x: max((r.gacha_ts for r in x.records), default=0),
                        reverse=True,
                    )
        return values

    # ── 分类属性 ──

    @property
    def char_pools(self) -> list[EfGachaPoolInfo]:
        """所有角色池（beginner + standard + special）"""
        return self.beginner_pools + self.standard_pools + self.special_pools

    @property
    def all_pools(self) -> list[EfGachaPoolInfo]:
        """所有卡池"""
        return self.char_pools + self.weapon_pools

    # ── 抽数统计 ──

    @property
    def beginner_total_pulls(self) -> int:
        return sum(pool.total_pulls for pool in self.beginner_pools)

    @property
    def standard_total_pulls(self) -> int:
        return sum(pool.total_pulls for pool in self.standard_pools)

    @property
    def standard_total_six(self) -> int:
        """常驻池总6★数"""
        return sum(pool.total_six_stars for pool in self.standard_pools)

    @property
    def standard_six_avg(self) -> float:
        """常驻池六星平均抽数

        计算方式：去掉免费十连，去掉距上次出6★的垫抽后，总付费抽数除以6★总数
        """
        six_count = self.standard_total_six
        if six_count == 0:
            return 0.0
        total_paid = sum(pool.paid_pulls for pool in self.standard_pools)
        return (total_paid - self.standard_pity) / six_count

    @property
    def special_total_pulls(self) -> int:
        return sum(pool.total_pulls for pool in self.special_pools)

    @property
    def special_total_six(self) -> int:
        """限定池总6★数"""
        return sum(pool.total_six_stars for pool in self.special_pools)

    @property
    def special_total_spook(self) -> int:
        """限定池总歪卡数"""
        return sum(pool.total_six_spook for pool in self.special_pools)

    @property
    def special_up_count(self) -> int:
        """限定池出UP角色总数"""
        return self.special_total_six - self.special_total_spook

    @property
    def special_up_avg(self) -> float:
        """限定池UP平均抽数

        计算方式：去掉免费十连，去掉距上次出UP的垫抽后，总付费抽数除以UP角色总数
        """
        up_count = self.special_up_count
        if up_count == 0:
            return 0.0
        total_paid = sum(pool.paid_pulls for pool in self.special_pools)
        # 去掉距上次出UP后的垫抽
        pity_after_last_up = self._special_up_pity()
        return (total_paid - pity_after_last_up) / up_count

    @property
    def char_total_pulls(self) -> int:
        """角色池总抽数"""
        return self.beginner_total_pulls + self.standard_total_pulls + self.special_total_pulls

    @property
    def weapon_total_pulls(self) -> int:
        """武器池总抽数"""
        return sum(pool.total_pulls for pool in self.weapon_pools)

    @property
    def total_pulls(self) -> int:
        """总抽数"""
        return self.char_total_pulls + self.weapon_total_pulls

    # ── 武库配额统计 ──

    @property
    def char_arsenal_quota_earned(self) -> int:
        """角色池武库配额产出总计（4★=20, 5★=200, 6★=2000）"""
        return sum(pool.arsenal_quota_earned for pool in self.char_pools)

    @property
    def weapon_arsenal_quota_consumed(self) -> int:
        """武器池武库配额消耗总计（每十连 1980）"""
        return sum(pool.arsenal_quota_consumed for pool in self.weapon_pools)

    @property
    def arsenal_quota_net(self) -> int:
        """武库配额净值（角色池产出 - 武器池消耗）"""
        return self.char_arsenal_quota_earned - self.weapon_arsenal_quota_consumed

    # ── STANDARD 保底（80抽小保底，独立） ──

    @property
    def standard_pity(self) -> int:
        """STANDARD 池当前已垫抽数（保底独立）"""
        if not self.standard_pools:
            return 0
        latest_pool = max(
            self.standard_pools,
            key=lambda p: max((r.gacha_ts for r in p.records), default=0),
            default=None,
        )
        return latest_pool.pity_count if latest_pool else 0

    @property
    def standard_pity_remaining(self) -> int:
        """STANDARD 池距小保底还差多少抽（80 - 已垫）"""
        return max(0, 80 - self.standard_pity)

    # ── SPECIAL 保底（小保底80跨池继承，大保底120每池独立） ──

    def _special_all_pulls_chronological(self) -> list[tuple[EfGachaPull, str]]:
        """所有 SPECIAL 池的抽卡记录按时间正序排列

        Returns:
            list of (pull, pool_id) 元组
        """
        all_entries: list[tuple[int, int, EfGachaPull, str]] = []
        for pool in self.special_pools:
            for group in pool.records:
                for pull in group.pulls:
                    all_entries.append((group.gacha_ts, pull.seq_id, pull, pool.pool_id))
        all_entries.sort(key=lambda x: (x[0], x[1]))
        return [(entry[2], entry[3]) for entry in all_entries]

    @property
    def special_pity(self) -> int:
        """SPECIAL 池跨池小保底已垫抽数（排除 isFree）

        小保底计数跨所有 SPECIAL 池共享继承。
        从最新记录往回数，跳过 isFree，
        遇到非免费 6★ 停止。
        """
        all_pulls = self._special_all_pulls_chronological()
        count = 0
        for pull, _ in reversed(all_pulls):
            if pull.is_free:
                continue
            if pull.rarity == 6:
                return count
            count += 1
        return count

    @property
    def special_pity_remaining(self) -> int:
        """SPECIAL 池距小保底（80）还差多少抽"""
        return max(0, 80 - self.special_pity)

    def special_pool_up_pity_remaining(self, pool: EfGachaPoolInfo) -> int:
        """指定 SPECIAL 卡池距大保底（120次必出UP 6★）还差多少抽

        大保底每个卡池独立，最多120次寻访必出当期UP 6★。
        排除 isFree 抽。
        """
        return max(0, 120 - pool.up_pity_count)

    def _special_up_pity(self) -> int:
        """限定池距上次出UP后的付费抽数

        从最新记录往回数，跳过 isFree，直到遇到非免费的 UP 6★。
        """
        all_pulls = self._special_all_pulls_chronological()
        count = 0
        for pull, pool_id in reversed(all_pulls):
            if pull.is_free:
                continue
            # 找到对应卡池的 up_six_chars
            pool_obj = next((p for p in self.special_pools if p.pool_id == pool_id), None)
            if pool_obj and pull.rarity == 6 and pull.item_id in pool_obj.up_six_chars:
                return count
            count += 1
        return count

    @property
    def weapon_total_six(self) -> int:
        """武器池总6★数"""
        return sum(pool.total_six_stars for pool in self.weapon_pools)

    @property
    def weapon_total_spook(self) -> int:
        """武器池总歪卡数"""
        return sum(pool.total_six_spook for pool in self.weapon_pools)

    @property
    def weapon_up_count(self) -> int:
        """武器池出UP武器总数"""
        return self.weapon_total_six - self.weapon_total_spook

    @property
    def weapon_up_avg(self) -> float:
        """武器池UP平均抽数

        计算方式：去掉免费十连，去掉距上次出UP的垫抽后，总付费抽数除以UP武器总数
        """
        up_count = self.weapon_up_count
        if up_count == 0:
            return 0.0
        total_paid = sum(pool.paid_pulls for pool in self.weapon_pools)
        # 武器池各池独立保底，取最新池的垫抽
        pity_after_last_up = self._weapon_up_pity()
        return (total_paid - pity_after_last_up) / up_count

    def _weapon_up_pity(self) -> int:
        """武器池距上次出UP后的付费抽数

        武器池各池独立，从所有武器池的最新记录往回数。
        """
        all_entries: list[tuple[int, int, EfGachaPull, str]] = []
        for pool in self.weapon_pools:
            for group in pool.records:
                for pull in group.pulls:
                    all_entries.append((group.gacha_ts, pull.seq_id, pull, pool.pool_id))
        all_entries.sort(key=lambda x: (x[0], x[1]))

        count = 0
        for _, _, pull, pool_id in reversed(all_entries):
            if pull.is_free:
                continue
            pool_obj = next((p for p in self.weapon_pools if p.pool_id == pool_id), None)
            if pool_obj and pull.rarity == 6 and pull.item_id in pool_obj.up_six_chars:
                return count
            count += 1
        return count

    # ── 武器池保底（各池独立） ──

    @property
    def weapon_pity(self) -> int:
        """武器池水位（取最新记录所在池）"""
        if not self.weapon_pools:
            return 0
        latest_pool = max(
            self.weapon_pools,
            key=lambda p: max((r.gacha_ts for r in p.records), default=0),
            default=None,
        )
        return latest_pool.pity_count if latest_pool else 0
