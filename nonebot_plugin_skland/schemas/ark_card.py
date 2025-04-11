from typing import Any
from datetime import datetime

from pydantic import BaseModel
from nonebot.compat import model_validator

from .ark_models import (
    Skin,
    Medal,
    Tower,
    Status,
    Recruit,
    Routine,
    Building,
    Campaign,
    BaseCount,
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

    @property
    def trainee_char(self) -> str:
        trainee = self.building.training.trainee
        if self.building.training.training_state == "training" and trainee:
            return self.charInfoMap[trainee.charId].name
        return ""

    @model_validator(mode="after")
    def inject_uniequip_uris(cls, values) -> Any:
        from ..config import RES_DIR

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

            char.uniequip = (RES_DIR / "images" / "ark_card" / "uniequip" / f"{equip_id}.png").as_uri()
        if isinstance(values, dict):
            values["assistChars"] = assist_chars
            return values
        else:
            return values

    @model_validator(mode="after")
    def inject_manufacture_stoke(cls, values) -> Any:
        if isinstance(values, dict):
            building = values.get("building")
            formula_map = values.get("manufactureFormulaInfoMap")
        else:
            building = values.building
            formula_map = values.manufactureFormulaInfoMap

        if not building or not formula_map:
            return values

        stoke_max = 0
        stoke_count = 0
        for manu in building.manufactures:
            if manu.formulaId in formula_map:
                formula_weight = formula_map[manu.formulaId].weight
                stoke_max += int(manu.capacity / formula_weight)
                elapsed_time = datetime.now().timestamp() - manu.lastUpdateTime
                cost_time = formula_map[manu.formulaId].costPoint / manu.speed
                additional_complete = round(elapsed_time / cost_time)
                if datetime.now().timestamp() >= manu.completeWorkTime:
                    stoke_count += manu.capacity // formula_weight
                else:
                    to_be_processed = (manu.completeWorkTime - manu.lastUpdateTime) / (cost_time / manu.speed)
                    has_processed = to_be_processed - int(to_be_processed)
                    additional_complete = (elapsed_time - has_processed * cost_time) / cost_time
                    stoke_count += manu.complete + int(additional_complete) + 1

        manufacture_stoke = BaseCount(current=stoke_count, total=stoke_max)

        if isinstance(values, dict):
            values["building"].manufacture_stoke = manufacture_stoke
            return values
        else:
            values.building.manufacture_stoke = manufacture_stoke
            return values
