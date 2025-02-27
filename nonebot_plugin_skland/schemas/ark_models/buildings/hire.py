from pydantic import BaseModel

from .base import BuildingChar


class Hire(BaseModel):
    slotId: str
    level: int
    chars: list[BuildingChar]
    state: int
    refreshCount: int
    completeWorkTime: int
    slotState: int
