from pydantic import BaseModel


class BubbleInfo(BaseModel):
    add: int
    ts: int


class Bubble(BaseModel):
    normal: BubbleInfo
    assist: BubbleInfo


class BuildingChar(BaseModel):
    """基建进驻干员信息"""

    charId: str
    ap: int
    lastApAddTime: int
    index: int
    bubble: Bubble
    workTime: int


class Labor(BaseModel):
    """无人机"""

    maxValue: int
    value: int
    lastUpdateTime: int
    remainSecs: int


class Furniture(BaseModel):
    """家具持有数"""

    total: int
