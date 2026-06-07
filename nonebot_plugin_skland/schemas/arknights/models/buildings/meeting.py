from pydantic import BaseModel

from .base import BuildingChar


class Clue(BaseModel):
    """线索信息"""

    own: int
    received: int
    dailyReward: bool
    needReceive: int
    board: list[str]
    sharing: bool
    shareCompleteTime: int


class Meeting(BaseModel):
    """会客厅"""

    slotId: str
    level: int
    chars: list[BuildingChar]
    clue: Clue
    lastUpdateTime: int
    completeWorkTime: int
