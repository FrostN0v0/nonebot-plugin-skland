from pydantic import BaseModel

from .base import BuildingChar


class Control(BaseModel):
    slotId: str
    slotState: int
    level: int
    chars: list[BuildingChar]
