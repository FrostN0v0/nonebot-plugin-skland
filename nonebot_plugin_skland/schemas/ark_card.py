import math
from datetime import datetime

from nonebot.compat import PYDANTIC_V2
from pydantic import BaseModel, ConfigDict


class BaseCount(BaseModel):
    """
    获取/完成进度

    Attributes:
        current (int): 当前值。
        total (int): 总值/上限。
    """

    current: int
    total: int


class Avatar(BaseModel):
    """角色头像信息"""

    type: str
    id: str
    url: str


class Secretary(BaseModel):
    """助理干员信息"""

    charId: str
    skinId: str


class AP(BaseModel):
    """理智"""

    current: int
    max: int
    lastApAddTime: int
    completeRecoveryTime: int

    @property
    def ap_now(self) -> int:
        """计算当前理智 ap_now ,并确保不超过最大理智值。"""
        current_time = datetime.now().timestamp()
        ap_now = self.max - math.ceil((self.completeRecoveryTime - current_time) / 360)
        ap_now = min(ap_now, self.max)

        return ap_now


class Exp(BaseModel):
    """经验值"""

    current: int
    max: int


class Status(BaseModel):
    """
    角色状态信息

    Attributes:
        uid : 角色 UID
        name : 角色名称
        level : 等级
        avatar : 头像信息
        registerTs : 注册时间戳
        secretary : 助理干员信息
        ap :理智信息
        lastOnlineTs : 角色最后在线时间戳
        exp : 经验值
    """

    uid: str
    name: str
    level: int
    avatar: Avatar
    registerTs: int
    mainStageProgress: str
    secretary: Secretary
    resume: str
    subscriptionEnd: int
    ap: AP
    storeTs: int
    lastOnlineTs: int
    charCnt: int
    furnitureCnt: int
    skinCnt: int
    exp: Exp


class MedalLayout(BaseModel):
    """
    蚀刻章布局

    Attributes:
        id (str): 奖章的唯一标识符
        pos (List[int]): 奖章的坐标位置,包含两个整数值(x, y)
    """

    id: str
    pos: list[int]


class Medal(BaseModel):
    """
    佩戴蚀刻章信息。

    Attributes:
        type (str): 佩戴蚀刻章类型，自定义或者套装
        template (str): 蚀刻章模板
        templateMedalList (List): 模板蚀刻章列表
        customMedalLayout (List[MedalLayout]): 蚀刻章的自定义布局
        total (int): 拥有的蚀刻章总数
    """

    type: str
    template: str
    templateMedalList: list[MedalLayout]
    customMedalLayout: list[MedalLayout]
    total: int


class Equip(BaseModel):
    """
    干员装备技能

    Attributes:
        id : 技能 ID
        level : 等级
    """

    id: str
    level: int
    locked: bool


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


class Recruit(BaseModel):
    """
    公招信息

    Attributes:
        startTs : 开始时间戳
        finishTs : 结束时间戳
        state : 状态
    """

    startTs: int
    finishTs: int
    state: int


class CampaignRecord(BaseModel):
    """
    剿灭记录

    Attributes:
        campaignId : 剿灭 ID
        maxKills : 最大击杀数
    """

    campaignId: str
    maxKills: int


class Campaign(BaseModel):
    """剿灭作战信息"""

    records: list[CampaignRecord]
    reward: BaseCount


class TowerRecord(BaseModel):
    """
    保全派驻记录

    Attributes:
        towerId : 保全派驻 ID
        best : 最高进度
    """

    towerId: str
    best: int


class TowerReward(BaseModel):
    """保全派驻奖励进度"""

    higherItem: BaseCount
    lowerItem: BaseCount
    termTs: int


class Tower(BaseModel):
    """保全派驻信息"""

    records: list[TowerRecord]
    reward: TowerReward


class Routine(BaseModel):
    """
    日/周常任务完成进度

    Attributes:
        daily : 日常任务进度
        weekly : 周常任务进度
    """

    daily: BaseCount
    weekly: BaseCount


class ArkCard(BaseModel):
    # TODO: 增加基建相关信息解析
    status: Status
    medal: Medal
    assistChars: list[AssistChar]
    recruit: list[Recruit]
    campaign: Campaign
    routine: Routine

    if PYDANTIC_V2:
        model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    else:

        class Config:
            extra = "allow"
            arbitrary_types_allowed = True
