from pydantic import BaseModel

from .base import BuildingChar


class Dormitory(BaseModel):
    """宿舍"""

    slotId: str
    level: int
    chars: list[BuildingChar]
    comfort: int
