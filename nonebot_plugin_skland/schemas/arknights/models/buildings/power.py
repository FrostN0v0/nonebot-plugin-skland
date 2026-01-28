from pydantic import BaseModel

from .base import BuildingChar


class Power(BaseModel):
    """发电站"""

    slotId: str
    level: int
    chars: list[BuildingChar]
