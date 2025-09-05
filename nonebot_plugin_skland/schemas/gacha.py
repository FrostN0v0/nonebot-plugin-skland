from typing import Any

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
        last_six_star_index = -1
        for i in range(len(all_pulls_chronological) - 1, -1, -1):
            if all_pulls_chronological[i].rarity == 5:
                last_six_star_index = i
                break
        return last_six_star_index + 1


class GroupedGachaRecord(BaseModel):
    """分组后的抽卡记录"""

    pools: list[GachaPool]

    @model_validator(mode="before")
    def sort_pools(cls, values) -> Any:
        if "pools" in values:
            values["pools"] = sorted(values["pools"], key=lambda x: x.openTime, reverse=True)
        return values

    @property
    def limit_total_pulls(self) -> int:
        """限定池总抽卡数"""
        total_pulls = 0
        for pool in self.pools:
            if pool.gachaRuleType in [1, 2, 3, 8]:
                total_pulls += pool.total_pulls
        return total_pulls

    @property
    def norm_total_pulls(self) -> int:
        """标准池总抽卡数"""
        total_pulls = 0
        for pool in self.pools:
            if pool.gachaRuleType in [0, 5, 9]:
                total_pulls += pool.total_pulls
        return total_pulls

    @property
    def doub_total_pulls(self) -> int:
        """中坚总抽卡数"""
        total_pulls = 0
        for pool in self.pools:
            if pool.gachaRuleType in [4, 6, 7, 10]:
                total_pulls += pool.total_pulls
        return total_pulls

    @property
    def limit_pity(self) -> int:
        """限定池当前已垫"""
        all_limited_pulls = (
            pull
            for pool in self.pools
            if pool.gachaRuleType in [1, 2, 3, 8]
            for group in pool.records
            for pull in group.pulls
        )
        pity_count = 0
        for pull in all_limited_pulls:
            if pull.rarity == 5:
                break
            pity_count += 1

        return pity_count

    @property
    def norm_pity(self) -> int:
        """标准池当前已垫"""
        all_normal_pulls = (
            pull
            for pool in self.pools
            if pool.gachaRuleType in [0, 5, 9]
            for group in pool.records
            for pull in group.pulls
        )
        pity_count = 0
        for pull in all_normal_pulls:
            if pull.rarity == 5:
                break
            pity_count += 1

        return pity_count

    @property
    def doub_pity(self) -> int:
        """中坚当前已垫"""
        all_doujin_pulls = (
            pull
            for pool in self.pools
            if pool.gachaRuleType in [4, 6, 7, 10]
            for group in pool.records
            for pull in group.pulls
        )
        pity_count = 0
        for pull in all_doujin_pulls:
            if pull.rarity == 5:
                break
            pity_count += 1

        return pity_count

    @property
    def limit_total_six(self) -> int:
        """限定池总六星数"""
        total_six_stars = 0
        for pool in self.pools:
            if pool.gachaRuleType in [1, 2, 3, 8]:
                total_six_stars += pool.total_six_stars
        return total_six_stars

    @property
    def norm_total_six(self) -> int:
        """标准池总六星数"""
        total_six_stars = 0
        for pool in self.pools:
            if pool.gachaRuleType in [0, 5, 9]:
                total_six_stars += pool.total_six_stars
        return total_six_stars

    @property
    def doub_total_six(self) -> int:
        """中坚总六星数"""
        total_six_stars = 0
        for pool in self.pools:
            if pool.gachaRuleType in [4, 6, 7, 10]:
                total_six_stars += pool.total_six_stars
        return total_six_stars

    @property
    def limit_six_spook(self) -> int:
        """限定池六星歪数"""
        total_six_spook = 0
        for pool in self.pools:
            if pool.gachaRuleType in [1, 2, 3, 8]:
                total_six_spook += pool.total_six_spook
        return total_six_spook

    @property
    def norm_six_spook(self) -> int:
        """标准池六星歪数"""
        total_six_spook = 0
        for pool in self.pools:
            if pool.gachaRuleType in [0, 5, 9]:
                total_six_spook += pool.total_six_spook
        return total_six_spook

    @property
    def doub_six_spook(self) -> int:
        """中坚六星歪数"""
        total_six_spook = 0
        for pool in self.pools:
            if pool.gachaRuleType in [4, 6, 7, 10]:
                total_six_spook += pool.total_six_spook
        return total_six_spook

    @property
    def limit_six_avg(self) -> float:
        """限定池六星UP平均"""
        bare_six_consume = 0
        for pool in self.pools:
            if pool.gachaRuleType in [1, 2, 3, 8]:
                bare_six_consume += pool.bare_six_consume
        return round(bare_six_consume / self.limit_total_six, 1) if self.limit_total_six > 0 else 0.0

    @property
    def norm_six_avg(self) -> float:
        """标准池六星UP平均"""
        bare_six_consume = 0
        for pool in self.pools:
            if pool.gachaRuleType in [0, 5, 9]:
                bare_six_consume += pool.bare_six_consume
        return round(bare_six_consume / self.norm_total_six, 1) if self.norm_total_six > 0 else 0.0

    @property
    def doub_six_avg(self) -> float:
        """中坚六星UP平均"""
        bare_six_consume = 0
        for pool in self.pools:
            if pool.gachaRuleType in [4, 6, 7, 10]:
                bare_six_consume += pool.bare_six_consume
        return round(bare_six_consume / self.doub_total_six, 1) if self.doub_total_six > 0 else 0.0


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
