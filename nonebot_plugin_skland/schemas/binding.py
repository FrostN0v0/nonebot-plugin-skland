from typing import Any, Literal
from collections.abc import Sequence

from pydantic import BaseModel
from nonebot.compat import model_validator


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


BindingCardMode = Literal["overview", "bind_confirmation", "unbind_selection", "unbind_confirmation"]
BindingAccountState = Literal["bound", "pending_bind", "pending_update", "pending_unbind"]


class BindingRoleSnapshot(BaseModel):
    app_code: Literal["arknights", "endfield"]
    app_name: str
    nickname: str
    binding_uid: str
    game_role_id: str
    server_id: str
    server_name: str
    level: int | None
    is_skland_default: bool
    is_available: bool
    unavailable_reason: str | None


class BindingAccountSnapshot(BaseModel):
    skland_user_id: str
    roles: list[BindingRoleSnapshot]

    @classmethod
    def from_apps(cls, skland_user_id: str, apps: Sequence[BindingApp]) -> "BindingAccountSnapshot":
        roles: list[BindingRoleSnapshot] = []
        for app in apps:
            if app.appCode == "arknights":
                for character in app.bindingList:
                    roles.append(
                        BindingRoleSnapshot(
                            app_code="arknights",
                            app_name="明日方舟",
                            nickname=character.nickName,
                            binding_uid=character.uid,
                            game_role_id=character.uid,
                            server_id=character.channelMasterId,
                            server_name=character.channelName,
                            level=None,
                            is_skland_default=character.isDefault or app.defaultUid == character.uid,
                            is_available=not character.isDelete,
                            unavailable_reason="角色已删除" if character.isDelete else None,
                        )
                    )
            elif app.appCode == "endfield":
                for character in app.bindingList:
                    has_role_default = any(role.isDefault for role in character.roles)
                    use_parent_default = (
                        not has_role_default and app.defaultUid == character.uid and len(character.roles) == 1
                    )
                    for role in character.roles:
                        is_deleted = character.isDelete
                        is_available = not is_deleted and not role.isBanned
                        unavailable_reason = "角色已删除" if is_deleted else "角色已封禁" if role.isBanned else None
                        roles.append(
                            BindingRoleSnapshot(
                                app_code="endfield",
                                app_name="明日方舟：终末地",
                                nickname=role.nickname,
                                binding_uid=character.uid,
                                game_role_id=role.roleId,
                                server_id=role.serverId,
                                server_name=role.serverName,
                                level=role.level,
                                is_skland_default=role.isDefault or use_parent_default,
                                is_available=is_available,
                                unavailable_reason=unavailable_reason,
                            )
                        )
        return cls(skland_user_id=skland_user_id, roles=roles)


class BoundRoleCardItem(BindingRoleSnapshot):
    index: int | None
    is_local_default: bool

    @property
    def player_uid(self) -> str:
        return self.binding_uid if self.app_code == "arknights" else self.game_role_id

    @property
    def server_label(self) -> str:
        if self.app_code == "endfield" and self.server_name == "China":
            return "\u56fd\u670d"
        return self.server_name


class BoundRoleCardAccount(BaseModel):
    account_id: int | None
    index: int
    account_user_id: str | None
    account_hint: str
    state: BindingAccountState
    roles: list[BoundRoleCardItem]


class BoundRolesCard(BaseModel):
    mode: BindingCardMode
    accounts: list[BoundRoleCardAccount]


class BoundRoleKey(BaseModel):
    account_id: int | None
    account_user_id: str | None
    app_code: Literal["arknights", "endfield"]
    server_id: str
    game_role_id: str

    @model_validator(mode="before")
    @classmethod
    def ensure_account_identity(cls, values: Any) -> Any:
        if isinstance(values, dict) and values.get("account_id") is None and not values.get("account_user_id"):
            raise ValueError("a bound role key requires an account identity")
        return values


class BoundRolesPlan(BaseModel):
    card: BoundRolesCard
    planned_defaults: dict[Literal["arknights", "endfield"], BoundRoleKey]
