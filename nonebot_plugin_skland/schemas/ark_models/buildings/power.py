from pydantic import BaseModel

from .base import BuildingChar


class Power(BaseModel):
    slotId: str
    level: int
    chars: list[BuildingChar]
