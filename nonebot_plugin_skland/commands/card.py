"""角色卡片相关命令"""

import json

from nonebot.compat import model_dump
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, UniMessage
from nonebot_plugin_argot import Text, Argot, Image, ArgotEvent, on_argot

from ..schemas import Clue
from ..config import config
from ..player_data import get_ark_card
from ..exception import SklandException
from .selection import check_user_character
from ..utils.background import get_background_image
from ..render import render_ark_card, render_clue_board
from ..utils.message import send_reaction, send_request_error


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

    selected = await check_user_character(target_id, user_session, session, app_code="arknights", role_index=role_index)
    if selected is None:
        return
    user, ark_character = selected
    send_reaction(user_session, "processing")

    try:
        info = await get_ark_card(user, ark_character)
    except SklandException as error:
        await session.commit()
        await send_request_error(error)
        return
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
