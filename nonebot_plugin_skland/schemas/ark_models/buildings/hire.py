from pydantic import BaseModel

from .base import BuildingChar


class Hire(BaseModel):
    """人事办公室"""

    slotId: str
    level: int
    chars: list[BuildingChar]
    state: int
    refreshCount: int
    completeWorkTime: int
    slotState: int
