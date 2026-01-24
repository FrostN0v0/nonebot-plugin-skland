"""角色卡片相关命令"""

import json

from nonebot.compat import model_dump
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, UniMessage
from nonebot_plugin_argot import Text, Argot, Image, ArgotEvent, on_argot

from ..api import SklandAPI
from ..config import config
from ..schemas import CRED, Clue
from ..model import SkUser, Character
from ..render import render_ark_card, render_clue_board
from ..db_handler import get_default_arknights_character
from ..utils import send_reaction, get_background_image, refresh_cred_token_if_needed, refresh_access_token_if_needed


async def check_user_character(user_id: int, session: async_scoped_session) -> tuple[SkUser, Character]:
    """检查用户和角色绑定状态"""
    user = await session.get(SkUser, user_id)
    if not user:
        await UniMessage("未绑定 skland 账号").finish(at_sender=True)
    char = await get_default_arknights_character(user, session)
    if not char:
        await UniMessage("未绑定 arknights 账号").finish(at_sender=True)
    return user, char


async def card_handler(
    session: async_scoped_session,
    user_session: UserSession,
    target: Match[At | int],
):
    """角色卡片查询"""

    @refresh_cred_token_if_needed
    @refresh_access_token_if_needed
    async def get_character_info(user: SkUser, uid: str):
        return await SklandAPI.ark_card(CRED(cred=user.cred, token=user.cred_token), uid)

    if target.available:
        target_platform_id = target.result.target if isinstance(target.result, At) else target.result
        target_id = (await get_user(user_session.platform, str(target_platform_id))).id
    else:
        target_id = user_session.user_id

    user, ark_characters = await check_user_character(target_id, session)
    send_reaction(user_session, "processing")

    info = await get_character_info(user, str(ark_characters.uid))
    if not info:
        return
    background = await get_background_image()
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
    await session.commit()


@on_argot("clue")
async def clue_handler(event: ArgotEvent):
    """线索板查看"""
    argot_data = json.loads(event.extra["data"])
    img = await render_clue_board(Clue(**argot_data))
    await event.target.send(UniMessage.image(raw=img))
