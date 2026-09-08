"""Skland account and default-role management commands."""

from typing import cast
from collections import defaultdict

from sqlalchemy.exc import IntegrityError
from nonebot_plugin_user import UserSession
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_alconna import Arparma, UniMessage

from ..utils.message import send_reaction
from .selection import send_bound_roles_overview
from ..exception import AccountOperationInProgress
from ..account import (
    GAME_NAMES,
    sync_account,
    exclusive_account_operation,
)
from ..db_handler import (
    get_accounts,
    select_all_accounts,
    get_default_character,
    set_default_character,
    get_character_by_index,
)

_GAME_ALIASES = {
    "ark": "arknights",
    "arknights": "arknights",
    "ef": "endfield",
    "endfield": "endfield",
}


async def _handle_set_default(
    owner_id: int,
    game: str,
    index: int,
    user_session: UserSession,
    session: async_scoped_session,
) -> None:
    app_code = _GAME_ALIASES[game]
    target = await get_character_by_index(owner_id, app_code, index, session)
    if target is None:
        await session.rollback()
        await send_bound_roles_overview(
            owner_id,
            user_session,
            session,
            text="角色序号无效,请以最新 sk char 卡片为准",
        )
        return
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
        result = await sync_account(account_id, session)
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
                    result = await sync_account(account_id, session)
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
        index = cast("int", result.query("char.set.index"))
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
