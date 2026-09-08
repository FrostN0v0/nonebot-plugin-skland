"""Detached binding preparation and confirmed account mutations.

Callers hold ``exclusive_account_operation`` for the entire interaction. Preparation
releases read transactions before discovery or presentation; commits revalidate the
confirmed snapshots and persist changes in one transaction.
"""

from typing import Literal
from dataclasses import dataclass
from collections.abc import Mapping, Collection

from sqlalchemy.exc import IntegrityError
from nonebot_plugin_orm import async_scoped_session

from ..model import SkUser
from ..db_handler import get_accounts
from ..player_data import ark_card_data
from ..api import SklandAPI, SklandLoginAPI
from ..schemas import CRED, BoundRolesPlan, BindingCardMode, BindingAccountSnapshot
from ..account import apply_planned_defaults, build_bound_roles_plan, reconcile_account_characters
from ..exception import (
    LoginException,
    RequestException,
    UnauthorizedException,
    BindingStateChangedError,
    DuplicateAccountIdentityError,
    AccountIdentityResolutionError,
)


@dataclass(frozen=True, slots=True)
class PendingCredential:
    access_token: str | None
    cred: str
    cred_token: str
    skland_user_id: str


@dataclass(frozen=True, slots=True)
class AccountIdentityOverride:
    account_id: int
    original_skland_user_id: str | None
    resolved_skland_user_id: str


@dataclass(frozen=True, slots=True)
class _DetachedAccountCredential:
    account_id: int
    original_skland_user_id: str | None
    access_token: str | None
    cred: str
    cred_token: str


async def _resolve_pending_credential(value: str) -> PendingCredential:
    credential = value.strip()
    if len(credential) == 24:
        grant_code = await SklandLoginAPI.get_grant_code(credential, 0)
        cred = await SklandLoginAPI.get_cred(grant_code)
        skland_user_id = cred.userId or await SklandAPI.get_user_ID(cred)
        if not skland_user_id:
            raise RequestException("未能解析森空岛账号身份")
        return PendingCredential(
            access_token=credential,
            cred=cred.cred,
            cred_token=cred.token,
            skland_user_id=skland_user_id,
        )
    if len(credential) == 32:
        cred_token = await SklandLoginAPI.refresh_token(credential)
        cred = CRED(cred=credential, token=cred_token)
        skland_user_id = await SklandAPI.get_user_ID(cred)
        if not skland_user_id:
            raise RequestException("未能解析森空岛账号身份")
        return PendingCredential(
            access_token=None,
            cred=credential,
            cred_token=cred_token,
            skland_user_id=skland_user_id,
        )
    raise ValueError("token 或 cred 错误,请检查格式")


async def _resolve_existing_account_identity(account: _DetachedAccountCredential) -> str:
    cred = CRED(cred=account.cred, token=account.cred_token)
    try:
        return await SklandAPI.get_user_ID(cred)
    except UnauthorizedException:
        refreshed_token = await SklandLoginAPI.refresh_token(account.cred)
        return await SklandAPI.get_user_ID(CRED(cred=account.cred, token=refreshed_token))
    except LoginException:
        if not account.access_token:
            raise
        grant_code = await SklandLoginAPI.get_grant_code(account.access_token, 0)
        refreshed_cred = await SklandLoginAPI.get_cred(grant_code)
        return refreshed_cred.userId or await SklandAPI.get_user_ID(refreshed_cred)


async def _load_detached_accounts(
    owner_id: int,
    session: async_scoped_session,
) -> list[_DetachedAccountCredential]:
    try:
        accounts = await get_accounts(owner_id, session)
        return [
            _DetachedAccountCredential(
                account_id=account.id,
                original_skland_user_id=account.skland_user_id,
                access_token=account.access_token,
                cred=account.cred,
                cred_token=account.cred_token,
            )
            for account in accounts
        ]
    finally:
        await session.rollback()


async def _resolve_account_overrides(
    accounts: list[_DetachedAccountCredential],
    candidate_skland_user_id: str,
) -> tuple[int | None, list[AccountIdentityOverride]]:
    stored_ids = [account.original_skland_user_id for account in accounts if account.original_skland_user_id]
    if len(stored_ids) != len(set(stored_ids)):
        raise DuplicateAccountIdentityError

    direct = [account.account_id for account in accounts if account.original_skland_user_id == candidate_skland_user_id]
    if direct:
        return direct[0], []

    overrides: list[AccountIdentityOverride] = []
    resolved_ids: set[str] = set()
    target_account_id: int | None = None
    for account in accounts:
        try:
            resolved = await _resolve_existing_account_identity(account)
        except (LoginException, RequestException, UnauthorizedException) as error:
            raise AccountIdentityResolutionError from error
        if not resolved or resolved in resolved_ids:
            raise DuplicateAccountIdentityError
        resolved_ids.add(resolved)
        if resolved == candidate_skland_user_id:
            target_account_id = account.account_id
        if resolved != account.original_skland_user_id:
            overrides.append(
                AccountIdentityOverride(
                    account_id=account.account_id,
                    original_skland_user_id=account.original_skland_user_id,
                    resolved_skland_user_id=resolved,
                )
            )
    return target_account_id, overrides


@dataclass(frozen=True, slots=True)
class PreparedBinding:
    owner_id: int
    pending: PendingCredential
    snapshot: BindingAccountSnapshot
    target_account_id: int | None
    expected_identities: tuple[tuple[int, str | None], ...]
    identity_overrides: tuple[AccountIdentityOverride, ...]
    plan: BoundRolesPlan


@dataclass(frozen=True, slots=True)
class PreparedUnbind:
    owner_id: int
    account_ids: frozenset[int]
    plan: BoundRolesPlan


async def prepare_binding_candidate(
    value: str,
    session: async_scoped_session,
) -> tuple[PendingCredential, BindingAccountSnapshot]:
    await session.rollback()
    pending = await _resolve_pending_credential(value)
    apps = await SklandAPI.get_binding(CRED(cred=pending.cred, token=pending.cred_token))
    return pending, BindingAccountSnapshot.from_apps(pending.skland_user_id, apps)


async def load_bound_roles_plan(
    owner_id: int,
    session: async_scoped_session,
    *,
    mode: BindingCardMode,
    pending_snapshot: BindingAccountSnapshot | None = None,
    pending_account_id: int | None = None,
    pending_unbind_account_ids: Collection[int] = (),
    account_identity_overrides: Mapping[int, str] | None = None,
) -> BoundRolesPlan:
    try:
        return await build_bound_roles_plan(
            owner_id,
            session,
            mode=mode,
            pending_snapshot=pending_snapshot,
            pending_account_id=pending_account_id,
            pending_unbind_account_ids=pending_unbind_account_ids,
            account_identity_overrides=account_identity_overrides,
        )
    finally:
        await session.rollback()


async def prepare_account_binding(
    owner_id: int,
    pending: PendingCredential,
    snapshot: BindingAccountSnapshot,
    session: async_scoped_session,
    *,
    mode: Literal["add", "update", "upsert"],
) -> PreparedBinding:
    accounts = await _load_detached_accounts(owner_id, session)
    target_account_id, overrides = await _resolve_account_overrides(accounts, pending.skland_user_id)
    if mode == "add" and target_account_id is not None:
        raise ValueError("该森空岛账号已绑定,请使用 sk bind -u 更新")
    if mode == "update" and target_account_id is None:
        raise ValueError("未找到该森空岛账号,请去掉 -u 后重新绑定")
    try:
        plan = await load_bound_roles_plan(
            owner_id,
            session,
            mode="bind_confirmation",
            pending_snapshot=snapshot,
            pending_account_id=target_account_id,
            account_identity_overrides={
                override.account_id: override.resolved_skland_user_id for override in overrides
            },
        )
    except ValueError as error:
        raise DuplicateAccountIdentityError from error
    return PreparedBinding(
        owner_id=owner_id,
        pending=pending,
        snapshot=snapshot,
        target_account_id=target_account_id,
        expected_identities=tuple((account.account_id, account.original_skland_user_id) for account in accounts),
        identity_overrides=tuple(overrides),
        plan=plan,
    )


async def commit_account_binding(prepared: PreparedBinding, session: async_scoped_session) -> None:
    owner_id = prepared.owner_id
    pending = prepared.pending
    override_map = {override.account_id: override.resolved_skland_user_id for override in prepared.identity_overrides}
    try:
        async with session.begin():
            accounts = await get_accounts(owner_id, session)
            current_identities = tuple((account.id, account.skland_user_id) for account in accounts)
            latest_plan = await build_bound_roles_plan(
                owner_id,
                session,
                mode="bind_confirmation",
                pending_snapshot=prepared.snapshot,
                pending_account_id=prepared.target_account_id,
                account_identity_overrides=override_map,
            )
            if current_identities != prepared.expected_identities or latest_plan != prepared.plan:
                raise BindingStateChangedError(latest_plan)

            accounts_by_id = {account.id: account for account in accounts}
            for override in prepared.identity_overrides:
                account = accounts_by_id[override.account_id]
                if account.skland_user_id != override.original_skland_user_id:
                    raise BindingStateChangedError(latest_plan)
                account.skland_user_id = override.resolved_skland_user_id

            if prepared.target_account_id is None:
                target = SkUser(
                    owner_id=owner_id,
                    access_token=pending.access_token,
                    cred=pending.cred,
                    cred_token=pending.cred_token,
                    skland_user_id=pending.skland_user_id,
                )
                session.add(target)
                await session.flush()
            else:
                target = accounts_by_id[prepared.target_account_id]
                if pending.access_token is not None:
                    target.access_token = pending.access_token
                target.cred = pending.cred
                target.cred_token = pending.cred_token
                target.skland_user_id = pending.skland_user_id

            await reconcile_account_characters(target, prepared.snapshot, session)
            await apply_planned_defaults(owner_id, prepared.plan.planned_defaults, session)
            invalidated_account_ids = set(override_map) | {target.id}
    except (IntegrityError, KeyError, ValueError) as error:
        try:
            conflict_plan = await load_bound_roles_plan(
                owner_id,
                session,
                mode="bind_confirmation",
                pending_snapshot=prepared.snapshot,
                pending_account_id=prepared.target_account_id,
                account_identity_overrides=override_map,
            )
        except ValueError:
            conflict_plan = None
        raise BindingStateChangedError(conflict_plan) from error

    for account_id in invalidated_account_ids:
        await ark_card_data.invalidate_account(account_id)


async def prepare_account_unbind(
    owner_id: int,
    account_ids: Collection[int],
    session: async_scoped_session,
) -> PreparedUnbind:
    selected = frozenset(account_ids)
    try:
        plan = await load_bound_roles_plan(
            owner_id,
            session,
            mode="unbind_confirmation",
            pending_unbind_account_ids=selected,
        )
    except ValueError as error:
        raise BindingStateChangedError from error
    return PreparedUnbind(owner_id=owner_id, account_ids=selected, plan=plan)


async def commit_account_unbind(prepared: PreparedUnbind, session: async_scoped_session) -> None:
    try:
        async with session.begin():
            latest_plan = await build_bound_roles_plan(
                prepared.owner_id,
                session,
                mode="unbind_confirmation",
                pending_unbind_account_ids=prepared.account_ids,
            )
            if latest_plan != prepared.plan:
                raise BindingStateChangedError(latest_plan)
            accounts = await get_accounts(prepared.owner_id, session)
            accounts_by_id = {account.id: account for account in accounts}
            if not prepared.account_ids.issubset(accounts_by_id):
                raise BindingStateChangedError
            for account_id in prepared.account_ids:
                await session.delete(accounts_by_id[account_id])
    except (IntegrityError, KeyError, ValueError) as error:
        raise BindingStateChangedError from error

    for account_id in prepared.account_ids:
        await ark_card_data.invalidate_account(account_id)
