from datetime import datetime

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
    Equipment,
    AssistChar,
    ManufactureFormulaInfo,
)


class CharInfo(BaseModel):
    id: str
    name: str


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
    equipmentInfoMap: dict[str, Equipment]
    manufactureFormulaInfoMap: dict[str, ManufactureFormulaInfo]
    charInfoMap: dict[str, CharInfo]

    @property
    def recruit_finished(self) -> int:
        return len([recruit for recruit in self.recruit if recruit.state == 1])

    @property
    def recruit_complete_time(self) -> str:
        from ..render import format_timestamp

        finish_ts = max([recruit.finishTs for recruit in self.recruit])
        if finish_ts == -1:
            return "招募已全部完成"
        format_time = format_timestamp(finish_ts - datetime.now().timestamp())
        return f"{format_time}后全部完成"
