from pydantic import BaseModel

from .base import Equip


class Skill(BaseModel):
    """干员技能"""

    id: str
    specializeLevel: int


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
