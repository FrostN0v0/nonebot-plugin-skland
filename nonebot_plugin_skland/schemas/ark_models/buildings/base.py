from pydantic import BaseModel


class BubbleInfo(BaseModel):
    add: int
    ts: int


class Bubble(BaseModel):
    normal: BubbleInfo
    assist: BubbleInfo


class BuildingChar(BaseModel):
    charId: str
    ap: int
    lastApAddTime: int
    index: int
    bubble: Bubble
    workTime: int


class Labor(BaseModel):
    maxValue: int
    value: int
    lastUpdateTime: int
    remainSecs: int


class Furniture(BaseModel):
    total: int
