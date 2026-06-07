import math
from datetime import datetime

from pydantic import BaseModel


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

    @property
    def register_time(self) -> str:
        return datetime.fromtimestamp(self.registerTs).strftime("%Y-%m-%d")
