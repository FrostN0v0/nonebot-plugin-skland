"""抽卡记录基础模型"""

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
