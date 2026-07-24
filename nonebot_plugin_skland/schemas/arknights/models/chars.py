from pydantic import BaseModel

from .base import Equip
from ....filters import (
    ark_elite_icon_url,
    ark_skill_icon_url,
    ark_skin_portrait_url,
    ark_potential_icon_url,
)


class Skill(BaseModel):
    """干员技能"""

    id: str
    specializeLevel: int

    @property
    def icon(self) -> str:
        return ark_skill_icon_url(self.id)


class Character(BaseModel):
    """持有干员"""

    charId: str
    skinId: str
    level: int
    evolvePhase: int
    potentialRank: int
    mainSkillLvl: int
    skills: list[Skill]
    equip: list[Equip]
    favorPercent: int
    defaultSkillId: str
    gainTime: int
    defaultEquipId: str

    @property
    def effective_skin_id(self) -> str:
        return self.skinId or f"{self.charId}#1"

    @property
    def portrait(self) -> str:
        return ark_skin_portrait_url(self.effective_skin_id)

    @property
    def potential(self) -> str:
        return ark_potential_icon_url(self.potentialRank)

    @property
    def elite(self) -> str:
        return ark_elite_icon_url(self.evolvePhase)

    @property
    def level_text(self) -> str:
        return str(self.level)
