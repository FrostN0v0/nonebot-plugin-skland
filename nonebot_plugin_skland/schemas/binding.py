from typing import Any

from pydantic import BaseModel


class Role(BaseModel):
    serverId: str
    roleId: str
    nickname: str
    level: int
    isDefault: bool
    isBanned: bool
    serverType: str
    serverName: str


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
    roles: list[Role]
    defaultRole: Any | None


class BindingApp(BaseModel):
    appCode: str
    appName: str
    bindingList: list[BindingCharacter]
    defaultUid: str | None = None
