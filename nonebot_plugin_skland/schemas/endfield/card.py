from typing import Any

from pydantic import Field, BaseModel


class KeyValuePair(BaseModel):
    """键值对模型（用于枚举类型）"""

    key: str = ""
    value: str = ""


class MainMission(BaseModel):
    """主线任务"""

    id: str = ""
    description: str = ""


class PlayerBase(BaseModel):
    """玩家基础信息"""

    serverName: str = ""
    roleId: str = ""
    name: str = ""
    createTime: str = ""
    saveTime: str = ""
    lastLoginTime: str = ""
    exp: int = 0
    level: int = 0
    worldLevel: int = 0
    gender: int = 0
    avatarUrl: str = ""
    mainMission: MainMission = Field(default_factory=MainMission)
    charNum: int = 0
    weaponNum: int = 0
    docNum: int = 0


class SkillDescLevelParams(BaseModel):
    """技能等级参数"""

    level: str = ""
    params: dict[str, str] = Field(default_factory=dict)


class Skill(BaseModel):
    """技能信息"""

    id: str = ""
    name: str = ""
    type: KeyValuePair = Field(default_factory=KeyValuePair)
    property: KeyValuePair = Field(default_factory=KeyValuePair)
    iconUrl: str = ""
    desc: str = ""
    descParams: dict[str, Any] = Field(default_factory=dict)
    descLevelParams: dict[str, SkillDescLevelParams] = Field(default_factory=dict)


class CharData(BaseModel):
    """角色基础数据"""

    id: str = ""
    name: str = ""
    avatarSqUrl: str = ""
    avatarRtUrl: str = ""
    rarity: KeyValuePair = Field(default_factory=KeyValuePair)
    profession: KeyValuePair = Field(default_factory=KeyValuePair)
    property: KeyValuePair = Field(default_factory=KeyValuePair)
    weaponType: KeyValuePair = Field(default_factory=KeyValuePair)
    skills: list[Skill] = Field(default_factory=list)
    labelType: str = ""
    illustrationUrl: str = ""
    tags: list[str] = Field(default_factory=list)


class UserSkill(BaseModel):
    """用户技能信息"""

    level: int = 0
    unlockTs: str = ""


class EquipSuit(BaseModel):
    """套组效果"""

    id: str = ""
    name: str = ""
    skillId: str = ""
    skillDesc: str = ""
    skillDescParams: dict[str, str] = Field(default_factory=dict)


class EquipData(BaseModel):
    """装备数据"""

    id: str = ""
    name: str = ""
    iconUrl: str = ""
    rarity: KeyValuePair = Field(default_factory=KeyValuePair)
    type: KeyValuePair = Field(default_factory=KeyValuePair)
    level: KeyValuePair = Field(default_factory=KeyValuePair)
    properties: list[str] = Field(default_factory=list)
    isAccessory: bool = False
    suit: EquipSuit | None = None
    function: str = ""
    pkg: str = ""
    mainEntry: KeyValuePair = Field(default_factory=KeyValuePair)
    mainEntryValue: str = ""
    subEntries: list[dict[str, Any]] = Field(default_factory=list)


class BodyEquip(BaseModel):
    """装备"""

    equipId: str = ""
    equipData: EquipData = Field(default_factory=EquipData)


class TacticalItemData(BaseModel):
    """战术道具数据"""

    id: str = ""
    name: str = ""
    iconUrl: str = ""
    rarity: KeyValuePair = Field(default_factory=KeyValuePair)
    activeEffectType: KeyValuePair = Field(default_factory=KeyValuePair)
    activeEffect: str = ""
    passiveEffect: str = ""


class TacticalItem(BaseModel):
    """战术道具"""

    tacticalItemId: str = ""
    tacticalItemData: TacticalItemData = Field(default_factory=TacticalItemData)


class WeaponData(BaseModel):
    """武器数据"""

    id: str = ""
    name: str = ""
    iconUrl: str = ""
    rarity: KeyValuePair = Field(default_factory=KeyValuePair)
    weaponType: KeyValuePair = Field(default_factory=KeyValuePair)
    attrType: KeyValuePair = Field(default_factory=KeyValuePair)
    desc: str = ""


class Weapon(BaseModel):
    """武器信息"""

    weaponData: WeaponData = Field(default_factory=WeaponData)
    level: int = 0
    refineLevel: int = 0
    breakthroughLevel: int = 0
    gem: Any = None
    # TODO


class Character(BaseModel):
    """角色完整信息"""

    charData: CharData = Field(default_factory=CharData)
    id: str = ""
    level: int = 0
    userSkills: dict[str, UserSkill] = Field(default_factory=dict)
    bodyEquip: BodyEquip | None = None
    armEquip: BodyEquip | None = None
    firstAccessory: BodyEquip | None = None
    secondAccessory: BodyEquip | None = None
    tacticalItem: TacticalItem | None = None
    evolvePhase: int = 0
    potentialLevel: int = 0
    weapon: Weapon = Field(default_factory=Weapon)
    gender: str = ""
    ownTs: str = ""


class AchieveDisplay(BaseModel):
    """成就展示"""

    type: int = 0
    achieveMedalId: str = ""


class Achieve(BaseModel):
    """成就信息"""

    achieveMedals: list[Any] = Field(default_factory=list)
    display: AchieveDisplay = Field(default_factory=AchieveDisplay)
    count: int = 0


class RoomReport(BaseModel):
    """房间报告"""

    char: list[str]
    output: dict[str, int]
    createdTimeTs: str


class Room(BaseModel):
    """飞船房间"""

    id: str = ""
    type: int = 0
    level: int = 0
    chars: list[Any] = Field(default_factory=list)
    reports: dict[str, RoomReport] | None


class SpaceShip(BaseModel):
    """飞船信息"""

    rooms: list[Room] = Field(default_factory=list)


class Settlement(BaseModel):
    """据点"""

    id: str = ""
    level: int = 0
    remainMoney: str = "0"
    officerCharIds: str = ""
    name: str = ""


class Collection(BaseModel):
    """收藏品"""

    levelId: str = ""
    puzzleCount: int = 0
    trchestCount: int = 0
    pieceCount: int = 0
    blackboxCount: int = 0


class Domain(BaseModel):
    """据点信息"""

    domainId: str = ""
    level: int = 0
    settlements: list[Settlement] = Field(default_factory=list)
    moneyMgr: str = ""
    collections: list[Collection] = Field(default_factory=list)
    factory: Any = None
    name: str = ""


class Dungeon(BaseModel):
    """体力"""

    curStamina: str = ""
    maxTs: str = ""
    maxStamina: str = ""


class BpSystem(BaseModel):
    """大月卡"""

    curLevel: int = 0
    maxLevel: int = 0


class DailyMission(BaseModel):
    """每日任务"""

    dailyActivation: int = 0
    maxDailyActivation: int = 0


class UserConfig(BaseModel):
    """用户配置"""

    charSwitch: bool = False
    charIds: list[str] = Field(default_factory=list)


class QuickAccess(BaseModel):
    """快速访问"""

    name: str = ""
    icon: str = ""
    link: str = ""


class EndfieldCard(BaseModel):
    """卡片详情数据"""

    base: PlayerBase = Field(default_factory=PlayerBase)
    chars: list[Character] = Field(default_factory=list)
    achieve: Achieve = Field(default_factory=Achieve)
    spaceShip: SpaceShip = Field(default_factory=SpaceShip)
    domain: list[Domain] = Field(default_factory=list)
    dungeon: Dungeon = Field(default_factory=Dungeon)
    bpSystem: BpSystem = Field(default_factory=BpSystem)
    dailyMission: DailyMission = Field(default_factory=DailyMission)
    config: UserConfig = Field(default_factory=UserConfig)
    currentTs: str = ""
    quickaccess: list[QuickAccess] = Field(default_factory=list)
