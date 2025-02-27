from pydantic import BaseModel

from .ark_models import (
    Medal,
    Tower,
    Status,
    Recruit,
    Routine,
    Building,
    Campaign,
    AssistChar,
)


class ArkCard(BaseModel):
    status: Status
    medal: Medal
    assistChars: list[AssistChar]
    recruit: list[Recruit]
    campaign: Campaign
    tower: Tower
    routine: Routine
    building: Building
