from typing import Any, ClassVar

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


class GroupedGachaRecord(BaseModel):
    """分组后的抽卡记录"""

    GACHA_RULE_TYPES: ClassVar[dict[str, list[int]]] = {"limit": [1, 2, 3, 8], "norm": [0, 5, 9], "doub": [4, 6, 7, 10]}

    pools: list[GachaPool]

    @model_validator(mode="before")
    def sort_pools(cls, values) -> Any:
        if "pools" in values:
            values["pools"] = sorted(values["pools"], key=lambda x: x.openTime, reverse=True)
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


class PerChar(BaseModel):
    rarityRank: int
    charIdList: list[str]


class UpCharInfo(BaseModel):
    perCharList: list[PerChar]


class AvailCharInfo(BaseModel):
    perAvailList: list[PerChar]


class GachaDetailInfo(BaseModel):
    upCharInfo: UpCharInfo | None = None
    availCharInfo: AvailCharInfo | None = None
    """UP角色信息"""


class GachaDetail(BaseModel):
    detailInfo: GachaDetailInfo
    """卡池详情"""


class GachaDetails(BaseModel):
    """抽卡详情"""

    gachaPoolDetail: GachaDetail
    gachaPoolId: str
