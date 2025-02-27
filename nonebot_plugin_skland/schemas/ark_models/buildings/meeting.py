from pydantic import BaseModel

from .base import BuildingChar


class Clue(BaseModel):
    own: int
    received: int
    dailyReward: bool
    needReceive: int
    board: list[str]
    sharing: bool
    shareCompleteTime: int


class Meeting(BaseModel):
    slotId: str
    level: int
    chars: list[BuildingChar]
    clue: Clue
    lastUpdateTime: int
    completeWorkTime: int
