from pydantic import Field, BaseModel


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
