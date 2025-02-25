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


class Exp(BaseModel):
    current: int
    max: int


class ArkCard(BaseModel):
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

    if PYDANTIC_V2:
        model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    else:

        class Config:
            extra = "allow"
            arbitrary_types_allowed = True
