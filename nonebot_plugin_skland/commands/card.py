"""角色卡片相关命令"""

import json

from nonebot.compat import model_dump
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, UniMessage
from nonebot_plugin_argot import Text, Argot, Image, ArgotEvent, on_argot

from ..schemas import Clue
from ..config import config
from ..model import SkUser, Character
from ..player_data import get_ark_card
from .char import send_bound_roles_overview
from ..render import render_ark_card, render_clue_board
from ..utils import send_reaction, get_background_image
from ..db_handler import get_accounts, get_default_character, get_character_by_index


async def check_user_character(
    owner_id: int,
    user_session: UserSession,
    session: async_scoped_session,
    *,
    role_index: int | None = None,
) -> tuple[SkUser, Character] | None:
    """Resolve the owner's selected Arknights role and its account."""
    requester_owner_id = user_session.user_id
    if role_index is not None:
        if owner_id != requester_owner_id:
            await session.rollback()
            await UniMessage("不能为其他用户指定角色").send(at_sender=True)
            return None
        character = await get_character_by_index(owner_id, "arknights", role_index, session)
        if character is not None:
            return character.account, character
        await session.rollback()
        await send_bound_roles_overview(
            owner_id,
            user_session,
            session,
            text="角色序号无效,请以最新 sk char 卡片为准",
        )
        return None

    character = await get_default_character(owner_id, "arknights", session)
    if character is not None:
        return character.account, character

    has_accounts = bool(await get_accounts(owner_id, session))
    await session.rollback()
    if owner_id != requester_owner_id:
        await UniMessage("目标用户尚未设置明日方舟默认角色").send(at_sender=True)
    elif has_accounts:
        await send_bound_roles_overview(
            owner_id,
            user_session,
            session,
            text="当前尚未设置明日方舟默认角色,请执行 sk char set ark <序号>",
        )
    else:
        await UniMessage("你还没有绑定森空岛账号").send(at_sender=True)
    return None


async def card_handler(
    session: async_scoped_session,
    user_session: UserSession,
    target: Match[At | int],
    *,
    role_index: int | None = None,
):
    """角色卡片查询"""

    if target.available:
        target_platform_id = target.result.target if isinstance(target.result, At) else target.result
        target_id = (await get_user(user_session.platform, str(target_platform_id))).id
    else:
        target_id = user_session.user_id

    selected = await check_user_character(target_id, user_session, session, role_index=role_index)
    if selected is None:
        return
    user, ark_character = selected
    send_reaction(user_session, "processing")

    info = await get_ark_card(user, ark_character)
    await session.commit()
    if not info:
        return
    background = await get_background_image("ark")
    image = await render_ark_card(info, background)
    if str(background).startswith("http"):
        argot_seg = [Text(str(background)), Image(url=str(background))]
    else:
        argot_seg = Image(path=str(background))
    msg = UniMessage.image(raw=image) + Argot(
        "background", argot_seg, command="background", expired_at=config.argot_expire
    )
    meeting = getattr(getattr(info, "building", None), "meeting", None)
    meeting_clue = getattr(meeting, "clue", None) if meeting else None
    if meeting_clue is not None:
        msg += Argot(
            "clue",
            command="clue",
            expired_at=config.argot_expire,
            extra={"data": json.dumps(model_dump(meeting_clue))},
        )
    send_reaction(user_session, "done")
    await msg.send(reply_to=True)


@on_argot("clue")
async def clue_handler(event: ArgotEvent):
    """线索板查看"""
    argot_data = json.loads(event.extra["data"])
    img = await render_clue_board(Clue(**argot_data))
    await event.target.send(UniMessage.image(raw=img))
