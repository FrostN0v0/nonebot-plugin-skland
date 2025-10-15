from typing import Any

from pydantic import BaseModel


class BindingCharacter(BaseModel):
    uid: str
    isOfficial: bool
    isDefault: bool
    channelMasterId: str
    channelName: str
    nickName: str
    isDelete: bool
    gameName: str
    gameId: int
    roles: list
    defaultRole: Any | None


class BindingApp(BaseModel):
    appCode: str
    appName: str
    bindingList: list[BindingCharacter]
    defaultUid: str | None = None
