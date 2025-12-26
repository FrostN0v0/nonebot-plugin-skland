from typing import Any, ClassVar
from collections.abc import Sequence

from pydantic import Field, BaseModel
from nonebot.compat import model_validator


class GachaCate(BaseModel):
    """卡池目录"""

    id: str
    """目录ID"""
    name: str
    """目录名称"""


class GachaInfo(BaseModel):
    """抽卡记录"""

    poolId: str
    """卡池ID"""
    poolName: str
    """卡池名称"""
    charId: str
    """角色ID"""
    charName: str
    """角色名称"""
    rarity: int
    """角色稀有度"""
    isNew: bool
    """是否为新角色"""
    gachaTs: str
    """抽卡时间"""
    pos: int
    """抽卡位置"""

    @property
    def gacha_ts_sec(self) -> int:
        """将毫秒级时间戳 (gachaTs) 转换为秒级时间戳。"""
        return int(self.gachaTs) // 1000


class GachaResponse(BaseModel):
    """Gacha Response Schema"""

    gacha_list: list[GachaInfo] = Field(default=[], alias="list")
    hasMore: bool

    @property
    def next_ts(self) -> str:
        """获取下一页的时间戳"""
        return self.gacha_list[-1].gachaTs if self.gacha_list else ""

    @property
    def next_pos(self) -> int:
        """获取下一页的抽卡位置"""
        return self.gacha_list[-1].pos if self.gacha_list else 0


class GachaTable(BaseModel):
    gachaPoolId: str
    gachaPoolName: str
    openTime: int
    endTime: int
    gachaRuleType: int


class GachaPull(BaseModel):
    """
    代表单次抽卡记录的数据模型
    """

    pool_name: str
    char_id: str
    char_name: str
    rarity: int
    is_new: bool
    pos: int


class GachaGroup(BaseModel):
    """
    代表在同一时间戳下的一组抽卡记录（例如一次十连抽）
    """

    gacha_ts: int
    pulls: list[GachaPull]

    @model_validator(mode="before")
    @classmethod
    def sort_pulls(cls, values) -> Any:
        if "pulls" in values:
            values["pulls"] = sorted(values["pulls"], key=lambda x: x.pos, reverse=True)
        return values


class GachaPool(GachaTable):
    up_five_chars: list[str]
    """UP五星角色列表"""
    up_six_chars: list[str]
    """UP六星角色列表"""
    records: list[GachaGroup]
    """该卡池的抽卡记录"""

    @model_validator(mode="before")
    @classmethod
    def sort_records(cls, values) -> Any:
        if "records" in values:
            values["records"] = sorted(values["records"], key=lambda x: x.gacha_ts, reverse=True)
        return values

    @property
    def total_pulls(self) -> int:
        """该卡池的总抽卡次数"""
        return sum(len(record.pulls) for record in self.records)

    @property
    def total_six_spook(self) -> int:
        """该卡池的总六星歪数"""
        return sum(
            1
            for record in self.records
            for pull in record.pulls
            if pull.rarity == 5 and pull.char_id not in self.up_six_chars
        )

    @property
    def total_six_stars(self) -> int:
        """该卡池的总六星角色数"""
        return sum(1 for record in self.records for pull in record.pulls if pull.rarity == 5)

    @property
    def bare_six_consume(self) -> int:
        """该卡池的UP六星角色净消耗(不含歪卡)"""
        all_pulls_chronological = []
        for record in reversed(self.records):
            all_pulls_chronological.extend(reversed(record.pulls))
        last_six_star_index = next(
            (i for i in range(len(all_pulls_chronological) - 1, -1, -1) if all_pulls_chronological[i].rarity == 5),
            -1,
        )
        return last_six_star_index + 1


class GachaTitleInfo(BaseModel):
    """抽卡称号信息"""

    title: str
    """称号名称"""
    six_star_rate: float
    """六星出货率（百分比）"""
    up_rate: float
    """UP率（百分比）"""
    total_score: float
    """综合得分（0-100）"""


class GroupedGachaRecord(BaseModel):
    """分组后的抽卡记录"""

    GACHA_RULE_TYPES: ClassVar[dict[str, list[int]]] = {"limit": [1, 2, 3, 8], "norm": [0, 5, 9], "doub": [4, 6, 7, 10]}

    pools: list[GachaPool]
    gacha_title: GachaTitleInfo | None = None
    """抽卡生涯评价称号"""

    @model_validator(mode="before")
    @classmethod
    def sort_pools(cls, values) -> Any:
        if "pools" in values:
            values["pools"] = sorted(values["pools"], key=lambda x: x.openTime, reverse=True)
        return values

    @model_validator(mode="after")
    @classmethod
    def calculate_gacha_title(cls, values) -> Any:
        """自动计算并填充抽卡称号"""
        if isinstance(values, dict):
            if values.get("gacha_title") is not None:
                return values
            return values
        else:
            if values.gacha_title is None:
                values.gacha_title = values.calculate_title()
            return values

    def _sum_by(self, attr: str, group: str) -> int:
        ids = self.GACHA_RULE_TYPES[group]
        return sum(getattr(pool, attr) for pool in self.pools if pool.gachaRuleType in ids)

    def _iter_pulls(self, group: str):
        ids = self.GACHA_RULE_TYPES[group]
        for pool in self.pools:
            if pool.gachaRuleType in ids:
                for grp in pool.records:
                    yield from grp.pulls

    def _pity(self, group: str) -> int:
        count = 0
        for pull in self._iter_pulls(group):
            if pull.rarity == 5:
                break
            count += 1
        return count

    @property
    def limit_total_pulls(self) -> int:
        return self._sum_by("total_pulls", "limit")

    @property
    def norm_total_pulls(self) -> int:
        return self._sum_by("total_pulls", "norm")

    @property
    def doub_total_pulls(self) -> int:
        return self._sum_by("total_pulls", "doub")

    @property
    def limit_pity(self) -> int:
        return self._pity("limit")

    @property
    def norm_pity(self) -> int:
        return self._pity("norm")

    @property
    def doub_pity(self) -> int:
        return self._pity("doub")

    @property
    def limit_total_six(self) -> int:
        return self._sum_by("total_six_stars", "limit")

    @property
    def norm_total_six(self) -> int:
        return self._sum_by("total_six_stars", "norm")

    @property
    def doub_total_six(self) -> int:
        return self._sum_by("total_six_stars", "doub")

    @property
    def limit_six_spook(self) -> int:
        return self._sum_by("total_six_spook", "limit")

    @property
    def norm_six_spook(self) -> int:
        return self._sum_by("total_six_spook", "norm")

    @property
    def doub_six_spook(self) -> int:
        return self._sum_by("total_six_spook", "doub")

    @property
    def limit_six_avg(self) -> float:
        total = self.limit_total_six
        return round(self._sum_by("bare_six_consume", "limit") / total, 1) if total else 0.0

    @property
    def norm_six_avg(self) -> float:
        total = self.norm_total_six
        return round(self._sum_by("bare_six_consume", "norm") / total, 1) if total else 0.0

    @property
    def doub_six_avg(self) -> float:
        total = self.doub_total_six
        return round(self._sum_by("bare_six_consume", "doub") / total, 1) if total else 0.0

    @property
    def total_pulls(self) -> int:
        """总抽卡次数"""
        return self.limit_total_pulls + self.norm_total_pulls + self.doub_total_pulls

    @property
    def total_six(self) -> int:
        """总六星数"""
        return self.limit_total_six + self.norm_total_six + self.doub_total_six

    @property
    def total_spook(self) -> int:
        """总歪卡数（不包含中坚）"""
        return self.limit_six_spook + self.norm_six_spook

    @property
    def non_doub_six(self) -> int:
        """除中坚外的六星数"""
        return self.limit_total_six + self.norm_total_six

    @property
    def six_star_rate(self) -> float:
        """六星出货率（百分比）"""
        if self.total_pulls == 0:
            return 0.0
        return round(self.total_six / self.total_pulls * 100, 1)

    @property
    def up_rate(self) -> float:
        """UP率（百分比）- 中坚卡池不参与计算"""
        if self.non_doub_six == 0:
            return 100.0  # 全是中坚卡池，默认100%
        return round((self.non_doub_six - self.total_spook) / self.non_doub_six * 100, 1)

    @staticmethod
    def _calculate_score(value: float, thresholds: Sequence[tuple[float, int]]) -> int:
        """根据阈值表计算得分"""
        return next((score for threshold, score in thresholds if value >= threshold), 0)

    def calculate_title(self) -> GachaTitleInfo:
        """
        计算抽卡生涯评价称号

        评分策略：
        1. 计算出货率得分（0-100）
        2. 计算UP率得分（0-100）
        3. 综合得分 = 出货率得分 * 0.7 + UP率得分 * 0.3
        4. 根据综合得分判定称号

        Returns:
            GachaTitleInfo: 称号信息
        """
        RATE_SCORES = [
            (4.5, 100),
            (4.0, 95),
            (3.5, 88),
            (3.2, 76),
            (3.0, 68),
            (2.8, 60),
            (2.6, 54),
            (2.4, 50),
            (2.2, 45),
            (2.0, 40),
            (1.8, 32),
            (1.5, 24),
            (1.2, 14),
            (0.0, 5),
        ]

        UP_SCORES = [
            (90, 100),
            (85, 95),
            (80, 88),
            (75, 80),
            (70, 70),
            (65, 60),
            (60, 50),
            (55, 40),
            (50, 30),
            (40, 20),
            (30, 10),
            (20, 5),
            (0, 0),
        ]
        TITLES = [
            (95, "绝世欧皇"),
            (80, "双层至尊欧皇"),
            (70, "传说级欧皇"),
            (56, "歪打正着的欧皇"),
            (48, "薛定谔的欧洲人"),
            (35, "脱欧入非"),
            (20, "面目全非"),
            (10, "非入骨髓"),
            (0, "绝世非酋"),
        ]

        six_star_rate = self.six_star_rate
        up_rate = self.up_rate

        total_score = round(
            self._calculate_score(six_star_rate, RATE_SCORES) * 0.7 + self._calculate_score(up_rate, UP_SCORES) * 0.3, 2
        )

        title = next(name for threshold, name in TITLES if total_score >= threshold)

        return GachaTitleInfo(title=title, six_star_rate=six_star_rate, up_rate=up_rate, total_score=total_score)
