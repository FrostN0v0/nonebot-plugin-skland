from pydantic import BaseModel

from .base import BuildingChar


class Manufacture(BaseModel):
    slotId: str
    level: int
    chars: list[BuildingChar]
    completeWorkTime: int
    lastUpdateTime: int
    formulaId: str
    capacity: int
    weight: int
    complete: int
    remain: int
    speed: float
