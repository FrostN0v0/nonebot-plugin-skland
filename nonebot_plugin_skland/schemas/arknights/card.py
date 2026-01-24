from typing import Any
from datetime import datetime

from pydantic import BaseModel
from nonebot.compat import model_validator

from .models import (
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
        from ...render import format_timestamp

        finish_ts = max([recruit.finishTs for recruit in self.recruit])
        if finish_ts == -1:
            return "招募已全部完成"
        format_time = format_timestamp(finish_ts - datetime.now().timestamp())
        return f"{format_time}后全部完成"

    @property
    def trainee_char(self) -> str:
        training = getattr(self.building, "training", None) if self.building else None
        trainee = getattr(training, "trainee", None) if training else None
        if trainee and trainee.charId in self.charInfoMap:
            return self.charInfoMap[trainee.charId].name
        return ""

    @model_validator(mode="after")
    @classmethod
    def inject_uniequip_uris(cls, values) -> Any:
        if isinstance(values, dict):
            assist_chars = values.get("assistChars", [])
            equipment_map = values.get("equipmentInfoMap", {})
        else:
            assist_chars = values.assistChars
            equipment_map = values.equipmentInfoMap

        for char in assist_chars:
            if char.equip and (equip := equipment_map.get(char.equip.id)):
                equip_id = equip.typeIcon
            else:
                equip_id = "original"

            char.uniequip = f"https://torappu.prts.wiki/assets/uniequip_direction/{equip_id}.png"
        if isinstance(values, dict):
            values["assistChars"] = assist_chars
            return values
        else:
            return values

    @model_validator(mode="after")
    @classmethod
    def inject_manufacture_stoke(cls, values) -> Any:
        if isinstance(values, dict):
            building = values.get("building")
            formula_map = values.get("manufactureFormulaInfoMap")
        else:
            building = values.building
            formula_map = values.manufactureFormulaInfoMap

        if not building or not formula_map:
            return values

        for slot in getattr(building, "manufactures", []) or []:
            if slot.formulaId and (info := formula_map.get(slot.formulaId)):
                slot.stoke_name = info.itemName
                if slot.weight != 0:
                    slot.stoke_speed = round(1 / slot.weight, 1)
        return values
