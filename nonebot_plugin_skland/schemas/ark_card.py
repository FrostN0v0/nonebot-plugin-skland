from pydantic import BaseModel

from .ark_models import (
    Skin,
    Medal,
    Tower,
    Status,
    Recruit,
    Routine,
    Building,
    Campaign,
    Character,
    AssistChar,
)


class ArkCard(BaseModel):
    status: Status
    medal: Medal
    assistChars: list[AssistChar]
    chars: list[Character]
    skins: list[Skin]
    recruit: list[Recruit]
    campaign: Campaign
    tower: Tower
    routine: Routine
    building: Building
