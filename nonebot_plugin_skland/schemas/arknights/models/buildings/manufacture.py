from pydantic import BaseModel

from .base import BuildingChar


class Manufacture(BaseModel):
    """制造站"""

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


class ManufactureFormulaInfo(BaseModel):
    """制造站配方"""

    id: str
    itemId: str
    weight: int
    costPoint: int
