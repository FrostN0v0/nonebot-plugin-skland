from pydantic import BaseModel

from .base import BuildingChar


class Dormitory(BaseModel):
    slotId: str
    level: int
    chars: list[BuildingChar]
    comfort: int
