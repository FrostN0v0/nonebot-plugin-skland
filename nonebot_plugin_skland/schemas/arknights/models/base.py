from pydantic import BaseModel


class BaseCount(BaseModel):
    """
    获取/完成进度

    Attributes:
        current (int): 当前值。
        total (int): 总值/上限。
    """

    current: int
    total: int


class Equip(BaseModel):
    """
    干员装备技能

    Attributes:
        id : 技能 ID
        level : 等级
    """

    id: str
    level: int
    locked: bool
