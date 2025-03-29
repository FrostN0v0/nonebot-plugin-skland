from pydantic import BaseModel

from .base import Equip
from ...config import RES_DIR, CACHE_DIR


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
        for symbol in ["@", "#"]:
            if symbol in self.skinId:
                portrait_id = self.skinId.replace(symbol, "_", 1)
                break
        img_path = CACHE_DIR / "portrait" / f"{portrait_id}.png"
        return img_path.as_uri()

    @property
    def potential(self) -> str:
        img_path = RES_DIR / "images" / "ark_card" / "potential" / f"potential_{self.potentialRank}.png"
        return img_path.as_uri()

    @property
    def skill(self) -> str:
        img_path = CACHE_DIR / "skill" / f"skill_icon_{self.skillId}.png"
        return img_path.as_uri()

    @property
    def evolve(self) -> str:
        img_path = RES_DIR / "images" / "ark_card" / "elite" / f"elite_{self.evolvePhase}.png"
        return img_path.as_uri()


class Equipment(BaseModel):
    id: str
    name: str
    typeIcon: str
