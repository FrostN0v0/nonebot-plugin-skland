import math
from datetime import datetime

from nonebot.compat import PYDANTIC_V2
from pydantic import BaseModel, ConfigDict


class Avatar(BaseModel):
    type: str
    id: str
    url: str


class Secretary(BaseModel):
    charId: str
    skinId: str


class AP(BaseModel):
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
    current: int
    max: int


class Status(BaseModel):
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


class ArkCard(BaseModel):
    status: Status

    if PYDANTIC_V2:
        model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    else:

        class Config:
            extra = "allow"
            arbitrary_types_allowed = True
