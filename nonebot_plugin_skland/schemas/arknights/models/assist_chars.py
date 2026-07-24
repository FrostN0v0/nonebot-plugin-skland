from pydantic import BaseModel

from .base import Equip
from ....filters import (
    ark_elite_icon_url,
    ark_skill_icon_url,
    ark_skin_portrait_url,
    ark_uniequip_icon_url,
    ark_potential_icon_url,
)


class AssistChar(BaseModel):
    """
    助战干员

    Attributes:
        charId : 干员 ID
        skinId : 皮肤 ID
        level : 等级
        evolvePhase : 升级阶段
        potentialRank : 潜能等级
        skillId : 技能 ID
        mainSkillLvl : 主技能等级
        specializeLevel : 专精等级
        equip : 装备技能
    """

    charId: str
    skinId: str
    level: int
    evolvePhase: int
    potentialRank: int
    skillId: str
    mainSkillLvl: int
    specializeLevel: int
    equip: Equip | None = None
    uniequip: str | None = None

    @property
    def portrait(self) -> str:
        return ark_skin_portrait_url(self.skinId)

    @property
    def potential(self) -> str:
        return ark_potential_icon_url(self.potentialRank)

    @property
    def skill(self) -> str:
        return ark_skill_icon_url(self.skillId)

    @property
    def evolve(self) -> str:
        return ark_elite_icon_url(self.evolvePhase)


class Equipment(BaseModel):
    id: str
    name: str
    typeIcon: str

    @property
    def icon(self) -> str:
        return ark_uniequip_icon_url(self.typeIcon)
