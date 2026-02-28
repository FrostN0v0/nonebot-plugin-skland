"""终末地抽卡记录基础模型"""

from enum import Enum
from typing import Any

from pydantic import Field, BaseModel
from nonebot.compat import model_validator


class EndfieldPoolType(Enum):
    """终末地卡池类型"""

    STANDARD = "E_CharacterGachaPoolType_Standard"
    SPECIAL = "E_CharacterGachaPoolType_Special"
    BEGINNER = "E_CharacterGachaPoolType_Beginner"
    WEAPON = ""


class EfCharGachaInfo(BaseModel):
    """终末地角色池 - 单条抽卡记录（API 原始响应）"""

    poolId: str
    """卡池ID"""
    poolName: str
    """卡池名称"""
    charId: str
    """角色ID"""
    charName: str
    """角色名称"""
    rarity: int
    """稀有度"""
    isFree: bool
    """是否免费"""
    isNew: bool
    """是否为新角色"""
    gachaTs: str
    """抽卡时间（毫秒级时间戳字符串）"""
    seqId: str
    """序列ID"""

    @property
    def item_id(self) -> str:
        return self.charId

    @property
    def item_name(self) -> str:
        return self.charName

    @property
    def item_type(self) -> str:
        return "char"

    @property
    def is_free_pull(self) -> bool:
        return self.isFree

    @property
    def gacha_ts_sec(self) -> int:
        """将毫秒级时间戳转换为秒级时间戳"""
        return int(self.gachaTs) // 1000

    @property
    def seq_id_int(self) -> int:
        """将 seqId 转换为整数，用于数据库存储"""
        return int(self.seqId)


class EfWeaponGachaInfo(BaseModel):
    """终末地武器池 - 单条抽卡记录（API 原始响应）"""

    poolId: str
    """卡池ID"""
    poolName: str
    """卡池名称"""
    weaponId: str
    """武器ID"""
    weaponName: str
    """武器名称"""
    weaponType: str
    """武器类型"""
    rarity: int
    """稀有度"""
    isNew: bool
    """是否为新武器"""
    gachaTs: str
    """抽卡时间（毫秒级时间戳字符串）"""
    seqId: str
    """序列ID"""

    @property
    def item_id(self) -> str:
        return self.weaponId

    @property
    def item_name(self) -> str:
        return self.weaponName

    @property
    def item_type(self) -> str:
        return "weapon"

    @property
    def is_free_pull(self) -> bool:
        return False

    @property
    def gacha_ts_sec(self) -> int:
        """将毫秒级时间戳转换为秒级时间戳"""
        return int(self.gachaTs) // 1000

    @property
    def seq_id_int(self) -> int:
        """将 seqId 转换为整数，用于数据库存储"""
        return int(self.seqId)


EfGachaInfo = EfCharGachaInfo | EfWeaponGachaInfo


class EfCharGachaResponse(BaseModel):
    """终末地角色池抽卡响应"""

    gacha_list: list[EfCharGachaInfo] = Field(default=[], alias="list")
    hasMore: bool

    @property
    def next_ts(self) -> str:
        return self.gacha_list[-1].gachaTs if self.gacha_list else ""

    @property
    def next_seq(self) -> str:
        return self.gacha_list[-1].seqId if self.gacha_list else ""


class EfWeaponGachaResponse(BaseModel):
    """终末地武器池抽卡响应"""

    gacha_list: list[EfWeaponGachaInfo] = Field(default=[], alias="list")
    hasMore: bool

    @property
    def next_ts(self) -> str:
        return self.gacha_list[-1].gachaTs if self.gacha_list else ""

    @property
    def next_seq(self) -> str:
        return self.gacha_list[-1].seqId if self.gacha_list else ""


EfGachaResponse = EfCharGachaResponse | EfWeaponGachaResponse



class EfGachaPull(BaseModel):
    """终末地单次抽卡记录（内部表示）"""

    pool_name: str
    item_id: str
    """物品ID（角色ID或武器ID）"""
    item_name: str
    """物品名称（角色名或武器名）"""
    item_type: str
    """物品类型: 'char' 或 'weapon'"""
    rarity: int
    is_new: bool
    is_free: bool = False
    """是否为免费抽取（角色池专用）"""
    seq_id: int


class EfGachaGroup(BaseModel):
    """终末地同一时间戳下的一组抽卡记录（一次十连）"""

    gacha_ts: int
    pulls: list[EfGachaPull]

    @model_validator(mode="before")
    @classmethod
    def sort_pulls(cls, values) -> Any:
        if "pulls" in values:
            values["pulls"] = sorted(values["pulls"], key=lambda x: x.seq_id, reverse=True)
        return values


class EfGachaContentChar(BaseModel):
    """Content API 中的角色/武器信息"""

    id: str
    name: str
    rarity: int
    """稀有度（1-indexed: 6=6★, 5=5★, 4=4★）"""


class EfGachaContentRotateItem(BaseModel):
    """Content API 中的轮换UP信息"""

    name: str
    times: int


class EfGachaContentPool(BaseModel):
    """Content API 中的卡池信息"""

    pool_gacha_type: str = ""
    pool_name: str = ""
    pool_type: str = ""
    up6_name: str = ""
    up5_name: str = ""
    all: list[EfGachaContentChar] = Field(default=[])
    rotate_list: list[EfGachaContentRotateItem] = Field(default=[])

    @property
    def up_six_char_ids(self) -> list[str]:
        """获取该卡池中所有UP六星角色的ID列表

        优先通过 rotate_list 匹配名称获取（含多期轮换UP），
        否则使用 up6_name 匹配。
        all 列表中 rarity 为 1-indexed（6=6★）。
        """
        if self.rotate_list:
            up_names = {r.name for r in self.rotate_list}
            return [c.id for c in self.all if c.rarity == 6 and c.name in up_names]
        if self.up6_name:
            return [c.id for c in self.all if c.rarity == 6 and c.name == self.up6_name]
        return []


class EfGachaContentResponse(BaseModel):
    """Content API 响应（单个卡池的UP角色信息）"""

    pool: EfGachaContentPool
    timezone: int = 8
