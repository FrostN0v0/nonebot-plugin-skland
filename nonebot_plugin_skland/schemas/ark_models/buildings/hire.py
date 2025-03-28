from datetime import datetime

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

    @property
    def refresh_complete_time(self) -> str:
        from ....render import format_timestamp

        if self.refreshCount == 3:
            return "可进行公开招募标签刷新"
        format_time = format_timestamp(datetime.now().timestamp() - self.completeWorkTime)
        return f"{format_time}后次数回满"
