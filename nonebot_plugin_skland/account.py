import asyncio
from typing import cast
from dataclasses import dataclass
from contextlib import asynccontextmanager
from collections.abc import Mapping, Collection, AsyncIterator

from sqlalchemy import select
from nonebot.compat import model_dump
from nonebot_plugin_orm import async_scoped_session

from .model import SkUser, Character, CharacterDefault
from .db_handler import get_account, get_accounts, get_user_characters, set_default_character, get_account_characters
from .schemas import (
    BoundRoleKey,
    BoundRolesCard,
    BoundRolesPlan,
    BindingCardMode,
    BoundRoleCardItem,
    BindingAccountState,
    BindingRoleSnapshot,
    BoundRoleCardAccount,
    BindingAccountSnapshot,
)

GAME_NAMES = {
    "arknights": "明日方舟",
    "endfield": "明日方舟：终末地",
}
_GAME_ORDER = {"arknights": 0, "endfield": 1}


class AccountOperationInProgress(RuntimeError):
    pass


@dataclass(slots=True)
class _ProjectedAccount:
    account_id: int | None
    account_user_id: str | None
    state: BindingAccountState
    roles: list[BindingRoleSnapshot]


@dataclass(slots=True)
class _ProjectedRole:
    account: _ProjectedAccount
    role: BindingRoleSnapshot


_active_owner_ids: set[int] = set()
_active_owner_lock = asyncio.Lock()


@asynccontextmanager
async def exclusive_account_operation(owner_id: int) -> AsyncIterator[None]:
    async with _active_owner_lock:
        if owner_id in _active_owner_ids:
            raise AccountOperationInProgress("an account-management operation is already active")
        _active_owner_ids.add(owner_id)
    try:
        yield
    finally:
        async with _active_owner_lock:
            _active_owner_ids.discard(owner_id)


def _persistent_role_snapshot(character: Character) -> BindingRoleSnapshot:
    return BindingRoleSnapshot(
        app_code=cast("str", character.app_code),
        app_name=GAME_NAMES[character.app_code],
        nickname=character.nickname,
        binding_uid=character.uid,
        game_role_id=character.role_id,
        server_id=character.channel_master_id,
        server_name=character.server_name,
        level=character.level,
        is_skland_default=character.is_skland_default,
        is_available=True,
        unavailable_reason=None,
    )


def _role_identity(projected: _ProjectedRole) -> tuple[int | None, str | None, str, str, str]:
    account_id = projected.account.account_id
    account_user_id = None if account_id is not None else projected.account.account_user_id
    return (
        account_id,
        account_user_id,
        projected.role.app_code,
        projected.role.server_id,
        projected.role.game_role_id,
    )


def _key_identity(key: BoundRoleKey) -> tuple[int | None, str | None, str, str, str]:
    account_user_id = None if key.account_id is not None else key.account_user_id
    return key.account_id, account_user_id, key.app_code, key.server_id, key.game_role_id


def _role_key(projected: _ProjectedRole) -> BoundRoleKey:
    account = projected.account
    return BoundRoleKey(
        account_id=account.account_id,
        account_user_id=(
            account.account_user_id if account.account_id is None or account.state == "pending_update" else None
        ),
        app_code=projected.role.app_code,
        server_id=projected.role.server_id,
        game_role_id=projected.role.game_role_id,
    )


async def reconcile_account_characters(
    account: SkUser,
    snapshot: BindingAccountSnapshot,
    session: async_scoped_session,
) -> set[str]:
    existing = await get_account_characters(account.id, session)
    existing_by_key = {
        (character.app_code, character.channel_master_id, character.role_id): character
        for character in existing
        if character.app_code in GAME_NAMES
    }
    default_character_ids = set(
        await session.scalars(
            select(CharacterDefault.character_id).where(CharacterDefault.owner_id == account.owner_id)
        )
    )

    available_roles: dict[tuple[str, str, str], BindingRoleSnapshot] = {}
    for role in snapshot.roles:
        if not role.is_available:
            continue
        key = (role.app_code, role.server_id, role.game_role_id)
        if key in available_roles:
            raise ValueError(f"duplicate role identity in binding snapshot: {key!r}")
        available_roles[key] = role

    removed_default_games: set[str] = set()
    for key, character in existing_by_key.items():
        if key in available_roles:
            continue
        if character.id in default_character_ids:
            removed_default_games.add(character.app_code)
        await session.delete(character)

    for key, role in available_roles.items():
        character = existing_by_key.get(key)
        if character is None:
            session.add(
                Character(
                    account_id=account.id,
                    uid=role.binding_uid,
                    role_id=role.game_role_id,
                    app_code=role.app_code,
                    channel_master_id=role.server_id,
                    server_name=role.server_name,
                    nickname=role.nickname,
                    level=role.level,
                    is_skland_default=role.is_skland_default,
                )
            )
            continue
        character.uid = role.binding_uid
        character.nickname = role.nickname
        character.server_name = role.server_name
        character.level = role.level
        character.is_skland_default = role.is_skland_default

    return removed_default_games


async def build_bound_roles_plan(
    owner_id: int,
    session: async_scoped_session,
    *,
    mode: BindingCardMode,
    pending_snapshot: BindingAccountSnapshot | None = None,
    pending_account_id: int | None = None,
    pending_unbind_account_ids: Collection[int] = (),
    account_identity_overrides: Mapping[int, str] | None = None,
) -> BoundRolesPlan:
    accounts = await get_accounts(owner_id, session)
    characters = await get_user_characters(owner_id, None, session)
    account_by_id = {account.id: account for account in accounts}
    overrides = dict(account_identity_overrides or {})

    unknown_override_ids = set(overrides) - set(account_by_id)
    if unknown_override_ids:
        raise ValueError(f"identity override references unknown accounts: {sorted(unknown_override_ids)!r}")

    unknown_unbind_ids = set(pending_unbind_account_ids) - set(account_by_id)
    if unknown_unbind_ids:
        raise ValueError(f"unbind selection references unknown accounts: {sorted(unknown_unbind_ids)!r}")
    if pending_snapshot is None and pending_account_id is not None:
        raise ValueError("pending_account_id requires pending_snapshot")
    if pending_snapshot is not None and pending_unbind_account_ids:
        raise ValueError("binding and unbinding projections cannot be combined")

    roles_by_account: dict[int, list[BindingRoleSnapshot]] = {account.id: [] for account in accounts}
    role_count_before = {"arknights": 0, "endfield": 0}
    for character in characters:
        if character.app_code not in GAME_NAMES:
            continue
        roles_by_account[character.account_id].append(_persistent_role_snapshot(character))
        role_count_before[character.app_code] += 1

    projected_accounts = [
        _ProjectedAccount(
            account_id=account.id,
            account_user_id=overrides.get(account.id, account.skland_user_id),
            state="pending_unbind" if account.id in pending_unbind_account_ids else "bound",
            roles=roles_by_account[account.id],
        )
        for account in accounts
    ]

    if pending_snapshot is not None:
        if pending_account_id is None:
            projected_accounts.append(
                _ProjectedAccount(
                    account_id=None,
                    account_user_id=pending_snapshot.skland_user_id,
                    state="pending_bind",
                    roles=list(pending_snapshot.roles),
                )
            )
        else:
            target = next(
                (account for account in projected_accounts if account.account_id == pending_account_id),
                None,
            )
            if target is None:
                raise ValueError("pending binding update references an unknown account")
            target.account_user_id = pending_snapshot.skland_user_id
            target.state = "pending_update"
            target.roles = list(pending_snapshot.roles)

    seen_account_user_ids: set[str] = set()
    for account in projected_accounts:
        if not account.account_user_id:
            continue
        if account.account_user_id in seen_account_user_ids:
            raise ValueError("duplicate Skland account identity in projected state")
        seen_account_user_ids.add(account.account_user_id)

    final_roles = [
        _ProjectedRole(account, role)
        for account in projected_accounts
        if account.account_id not in pending_unbind_account_ids
        for role in account.roles
        if role.is_available
    ]
    final_roles_by_identity = {_role_identity(role): role for role in final_roles}
    if len(final_roles_by_identity) != len(final_roles):
        raise ValueError("duplicate role identity in projected state")

    current_default_rows = (
        await session.execute(
            select(CharacterDefault, Character)
            .join(Character, Character.id == CharacterDefault.character_id)
            .join(SkUser, SkUser.id == Character.account_id)
            .where(CharacterDefault.owner_id == owner_id, SkUser.owner_id == owner_id)
        )
    ).all()
    current_defaults = {
        default.app_code: (
            character.account_id,
            None,
            character.app_code,
            character.channel_master_id,
            character.role_id,
        )
        for default, character in current_default_rows
    }

    planned_defaults: dict[str, BoundRoleKey] = {}
    for app_code in ("arknights", "endfield"):
        current_identity = current_defaults.get(app_code)
        if current_identity is not None and current_identity in final_roles_by_identity:
            planned_defaults[app_code] = _role_key(final_roles_by_identity[current_identity])
            continue
        if role_count_before[app_code] != 0:
            continue
        candidates = [role for role in final_roles if role.role.app_code == app_code]
        remote_defaults = [role for role in candidates if role.role.is_skland_default]
        selected: _ProjectedRole | None = None
        if len(remote_defaults) == 1:
            selected = remote_defaults[0]
        elif len(candidates) == 1:
            selected = candidates[0]
        if selected is not None:
            planned_defaults[app_code] = _role_key(selected)

    role_indexes = {"arknights": 0, "endfield": 0}
    card_accounts: list[BoundRoleCardAccount] = []
    for account_index, account in enumerate(projected_accounts, start=1):
        card_roles: list[BoundRoleCardItem] = []
        sorted_roles = sorted(
            account.roles,
            key=lambda role: (_GAME_ORDER[role.app_code], role.server_id, role.game_role_id),
        )
        for role in sorted_roles:
            index: int | None = None
            if role.is_available:
                role_indexes[role.app_code] += 1
                index = role_indexes[role.app_code]
            projected_role = _ProjectedRole(account, role)
            planned = planned_defaults.get(role.app_code)
            card_roles.append(
                BoundRoleCardItem(
                    **model_dump(role),
                    index=index,
                    is_local_default=planned is not None and _key_identity(planned) == _role_identity(projected_role),
                )
            )
        account_hint = f"••••{account.account_user_id[-4:]}" if account.account_user_id else "待同步"
        card_accounts.append(
            BoundRoleCardAccount(
                account_id=account.account_id,
                index=account_index,
                account_user_id=account.account_user_id,
                account_hint=account_hint,
                state=account.state,
                roles=card_roles,
            )
        )

    return BoundRolesPlan(
        card=BoundRolesCard(mode=mode, accounts=card_accounts),
        planned_defaults=cast("dict", planned_defaults),
    )


async def apply_planned_defaults(
    owner_id: int,
    planned_defaults: Mapping[str, BoundRoleKey],
    session: async_scoped_session,
) -> None:
    await session.flush()
    existing_defaults = {
        default.app_code: default
        for default in await session.scalars(select(CharacterDefault).where(CharacterDefault.owner_id == owner_id))
    }

    for app_code in ("arknights", "endfield"):
        key = planned_defaults.get(app_code)
        existing = existing_defaults.get(app_code)
        if key is None:
            if existing is not None:
                await session.delete(existing)
            continue

        account: SkUser | None
        if key.account_id is not None:
            account = await session.get(SkUser, key.account_id)
            if account is None or account.owner_id != owner_id:
                raise ValueError("planned default references an account outside the owner")
            if key.account_user_id is not None and account.skland_user_id != key.account_user_id:
                raise ValueError("planned default account identity changed")
        else:
            if key.account_user_id is None:
                raise ValueError("planned default has no account identity")
            account = await get_account(owner_id, key.account_user_id, session)
            if account is None:
                raise ValueError("planned default account was not created")

        character = await session.scalar(
            select(Character).where(
                Character.account_id == account.id,
                Character.app_code == app_code,
                Character.channel_master_id == key.server_id,
                Character.role_id == key.game_role_id,
            )
        )
        if character is None:
            raise ValueError("planned default role was not persisted")
        await set_default_character(owner_id, app_code, character.id, session)
