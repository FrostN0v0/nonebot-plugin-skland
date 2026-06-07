from pydantic import BaseModel

from .base import BuildingChar


class Control(BaseModel):
    """控制中枢"""

    slotId: str
    slotState: int
    level: int
    chars: list[BuildingChar]
