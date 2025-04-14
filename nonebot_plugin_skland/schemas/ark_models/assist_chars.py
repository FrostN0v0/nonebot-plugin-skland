from urllib.parse import quote

from nonebot import logger
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
        if not img_path.exists():
            encoded_id = quote(self.skinId, safe="")
            img_path = f"https://web.hycdn.cn/arknights/game/assets/char_skin/portrait/{encoded_id}.png"
            logger.debug(f"Portrait not found locally, using URL: {img_path}")
            return img_path
        return img_path.as_uri()

    @property
    def potential(self) -> str:
        img_path = RES_DIR / "images" / "ark_card" / "potential" / f"potential_{self.potentialRank}.png"
        return img_path.as_uri()

    @property
    def skill(self) -> str:
        img_path = CACHE_DIR / "skill" / f"skill_icon_{self.skillId}.png"
        if not img_path.exists():
            encoded_id = quote(self.skillId, safe="")
            img_path = f"https://web.hycdn.cn/arknights/game/assets/char_skill/{encoded_id}.png"
            logger.debug(f"Skill icon not found locally, using URL: {img_path}")
            return img_path
        return img_path.as_uri()

    @property
    def evolve(self) -> str:
        img_path = RES_DIR / "images" / "ark_card" / "elite" / f"elite_{self.evolvePhase}.png"
        return img_path.as_uri()


class Equipment(BaseModel):
    id: str
    name: str
    typeIcon: str
