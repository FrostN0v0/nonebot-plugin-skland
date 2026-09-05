"""Skland account and default-role management commands."""

from dataclasses import dataclass
from collections import defaultdict

from nonebot import logger
from sqlalchemy.exc import IntegrityError
from nonebot_plugin_user import UserSession
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_alconna import Arparma, UniMessage

from ..model import SkUser
from ..api import SklandAPI
from ..player_data import ark_card_data
from ..render import render_bound_roles_card
from ..schemas import CRED, BindingAccountSnapshot
from ..utils import (
    send_reaction,
    refresh_cred_token_with_error_return,
    refresh_access_token_with_error_return,
)
from ..db_handler import (
    get_accounts,
    get_user_characters,
    select_all_accounts,
    get_default_character,
    set_default_character,
)
from ..account import (
    GAME_NAMES,
    AccountOperationInProgress,
    apply_planned_defaults,
    build_bound_roles_plan,
    exclusive_account_operation,
    reconcile_account_characters,
)

_GAME_ALIASES = {
    "ark": "arknights",
    "arknights": "arknights",
    "ef": "endfield",
    "endfield": "endfield",
}


@dataclass(frozen=True, slots=True)
class _SyncResult:
    success: bool
    removed_default_games: frozenset[str] = frozenset()
    error: str | None = None


@refresh_cred_token_with_error_return
@refresh_access_token_with_error_return
async def _fetch_account_snapshot(account: SkUser) -> BindingAccountSnapshot:
    cred = CRED(cred=account.cred, token=account.cred_token)
    apps = await SklandAPI.get_binding(cred)
    skland_user_id = account.skland_user_id or await SklandAPI.get_user_ID(cred)
    return BindingAccountSnapshot.from_apps(skland_user_id, apps)


async def _sync_account(account_id: int, session: async_scoped_session) -> _SyncResult:
    account = await session.get(SkUser, account_id)
    if account is None:
        await session.rollback()
        return _SyncResult(False, error="账号已不存在")
    owner_id = account.owner_id
    original_skland_user_id = account.skland_user_id
    detached_account = SkUser(
        id=account.id,
        owner_id=account.owner_id,
        access_token=account.access_token,
        cred=account.cred,
        cred_token=account.cred_token,
        skland_user_id=account.skland_user_id,
    )
    await session.rollback()

    snapshot = await _fetch_account_snapshot(detached_account)
    if isinstance(snapshot, str):
        return _SyncResult(False, error=snapshot)

    try:
        projected_plan = await build_bound_roles_plan(
            owner_id,
            session,
            mode="overview",
            pending_snapshot=snapshot,
            pending_account_id=account_id,
            account_identity_overrides={account_id: snapshot.skland_user_id},
        )
        current = await session.get(SkUser, account_id)
        if current is None or current.owner_id != owner_id or current.skland_user_id != original_skland_user_id:
            raise ValueError("account changed during synchronization")
        current.access_token = detached_account.access_token
        current.cred = detached_account.cred
        current.cred_token = detached_account.cred_token
        current.skland_user_id = snapshot.skland_user_id
        removed_defaults = await reconcile_account_characters(current, snapshot, session)
        await apply_planned_defaults(owner_id, projected_plan.planned_defaults, session)
        await session.commit()
    except (IntegrityError, ValueError) as error:
        await session.rollback()
        return _SyncResult(False, error=str(error))

    await ark_card_data.invalidate_account(account_id)
    return _SyncResult(True, frozenset(removed_defaults))


async def send_bound_roles_overview(
    owner_id: int,
    user_session: UserSession,
    session: async_scoped_session,
    *,
    text: str | None = None,
) -> bool:
    try:
        plan = await build_bound_roles_plan(owner_id, session, mode="overview")
    finally:
        await session.rollback()
    if not plan.card.accounts:
        await UniMessage(text or "你还没有绑定森空岛账号").send(at_sender=True)
        return False
    try:
        image = await render_bound_roles_card(plan.card)
    except Exception:
        logger.exception("Failed to render the bound-role overview")
        await UniMessage(text or "角色列表渲染失败").send(at_sender=True)
        return False
    instruction = "切换默认角色: sk char set ark <序号> / sk char set ef <序号>"
    message_text = f"{text}\n{instruction}" if text else instruction
    await UniMessage.image(raw=image).text(f"\n{message_text}").send(reply_to=True, at_sender=True)
    return True


async def _handle_set_default(
    owner_id: int,
    game: str,
    index: int,
    user_session: UserSession,
    session: async_scoped_session,
) -> None:
    app_code = _GAME_ALIASES[game]
    characters = await get_user_characters(owner_id, app_code, session)
    if index < 1 or index > len(characters):
        await session.rollback()
        await send_bound_roles_overview(
            owner_id,
            user_session,
            session,
            text="角色序号无效,请以最新 sk char 卡片为准",
        )
        return
    target = characters[index - 1]
    current = await get_default_character(owner_id, app_code, session)
    if current is not None and current.id == target.id:
        await session.rollback()
        await UniMessage("该角色已是当前游戏的默认角色").send(at_sender=True)
        return

    nickname = target.nickname
    server_name = target.server_name
    try:
        await set_default_character(owner_id, app_code, target.id, session)
        await session.commit()
    except (IntegrityError, ValueError):
        await session.rollback()
        await send_bound_roles_overview(
            owner_id,
            user_session,
            session,
            text="角色数据已变化,请以最新 sk char 卡片为准",
        )
        return

    await send_bound_roles_overview(
        owner_id,
        user_session,
        session,
        text=f"默认角色已切换为:{GAME_NAMES[app_code]} / {nickname} / {server_name}",
    )


async def _handle_update(
    owner_id: int,
    user_session: UserSession,
    session: async_scoped_session,
) -> None:
    accounts = await get_accounts(owner_id, session)
    account_ids = [account.id for account in accounts]
    await session.rollback()
    if not account_ids:
        await UniMessage("你还没有绑定森空岛账号").send(at_sender=True)
        return

    success_count = 0
    fail_count = 0
    removed_default_games: set[str] = set()
    for account_id in account_ids:
        result = await _sync_account(account_id, session)
        if result.success:
            success_count += 1
            removed_default_games.update(result.removed_default_games)
        else:
            fail_count += 1

    lines = ["角色更新完成", f"成功: {success_count}, 失败: {fail_count}"]
    if removed_default_games:
        game_names = "、".join(GAME_NAMES[game] for game in sorted(removed_default_games))
        lines.append(f"以下游戏的默认角色已失效,请重新选择:{game_names}")
    await send_bound_roles_overview(owner_id, user_session, session, text="\n".join(lines))


async def _handle_update_all(session: async_scoped_session) -> None:
    accounts = await select_all_accounts(session)
    account_ids_by_owner: dict[int, list[int]] = defaultdict(list)
    for account in accounts:
        account_ids_by_owner[account.owner_id].append(account.id)
    await session.rollback()

    success_count = 0
    fail_count = 0
    for owner_id, account_ids in account_ids_by_owner.items():
        try:
            async with exclusive_account_operation(owner_id):
                for account_id in account_ids:
                    result = await _sync_account(account_id, session)
                    if result.success:
                        success_count += 1
                    else:
                        fail_count += 1
        except AccountOperationInProgress:
            fail_count += len(account_ids)
    await UniMessage(f"全体角色更新完成\n成功: {success_count}, 失败: {fail_count}").send(at_sender=True)


async def char_handler(
    user_session: UserSession,
    session: async_scoped_session,
    result: Arparma,
    is_superuser: bool,
) -> None:
    if result.find("char.update.all"):
        if not is_superuser:
            await UniMessage.text("该指令仅超管可用").send()
            return
        await _handle_update_all(session)
        return

    if result.find("char.update"):
        try:
            async with exclusive_account_operation(user_session.user_id):
                send_reaction(user_session, "processing")
                await _handle_update(user_session.user_id, user_session, session)
                send_reaction(user_session, "done")
        except AccountOperationInProgress:
            await UniMessage("已有账号管理操作进行中").send(at_sender=True)
        return

    if result.find("char.set"):
        game = str(result.query("char.set.game"))
        index = int(result.query("char.set.index"))
        try:
            async with exclusive_account_operation(user_session.user_id):
                await _handle_set_default(
                    user_session.user_id,
                    game,
                    index,
                    user_session,
                    session,
                )
        except AccountOperationInProgress:
            await UniMessage("已有账号管理操作进行中").send(at_sender=True)
        return

    await send_bound_roles_overview(user_session.user_id, user_session, session)
