from pydantic import BaseModel

from .base import Equip


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
    equip: Equip
    uniequip: str | None = None

    @property
    def portrait(self) -> str:
        from ...utils import get_portrait

        return get_portrait(self)
