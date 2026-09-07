"""Shared role selection and account-overview feedback for commands."""

from typing import Literal

from nonebot import logger
from nonebot_plugin_user import UserSession
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_orm import async_scoped_session

from ..model import SkUser, Character
from ..account import build_bound_roles_plan
from ..render import render_bound_roles_card
from ..db_handler import get_accounts, get_default_character, get_character_by_index


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
    instruction = (
        "临时选角: 查询、签到、状态及抽卡导入命令可追加 -r <序号>\n"
        "切换默认角色: sk char set ark <序号> / sk char set ef <序号>"
    )
    message_text = f"{text}\n{instruction}" if text else instruction
    await UniMessage.image(raw=image).text(f"\n{message_text}").send(reply_to=True, at_sender=True)
    return True


async def check_user_character(
    owner_id: int,
    user_session: UserSession,
    session: async_scoped_session,
    *,
    app_code: Literal["arknights", "endfield"],
    role_index: int | None = None,
) -> tuple[SkUser, Character] | None:
    """Resolve a permitted role and its account without changing defaults."""
    requester_owner_id = user_session.user_id
    if role_index is not None:
        if owner_id != requester_owner_id:
            await session.rollback()
            await UniMessage("不能为其他用户指定角色").send(at_sender=True)
            return None
        character = await get_character_by_index(owner_id, app_code, role_index, session)
        if character is not None:
            return character.account, character
        await session.rollback()
        await send_bound_roles_overview(owner_id, user_session, session, text="角色序号无效,请以最新 sk char 卡片为准")
        return None

    character = await get_default_character(owner_id, app_code, session)
    if character is not None:
        return character.account, character
    has_accounts = bool(await get_accounts(owner_id, session))
    await session.rollback()
    game_name = "明日方舟" if app_code == "arknights" else "终末地"
    if owner_id != requester_owner_id:
        await UniMessage(f"目标用户尚未设置{game_name}默认角色").send(at_sender=True)
    elif has_accounts:
        game_token = "ark" if app_code == "arknights" else "ef"
        await send_bound_roles_overview(
            owner_id,
            user_session,
            session,
            text=f"当前尚未设置{game_name}默认角色,请执行 sk char set {game_token} <序号>",
        )
    else:
        await UniMessage("你还没有绑定森空岛账号").send(at_sender=True)
    return None
