from nonebot_plugin_argot import Argot
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Text, Image, Match, UniMessage

from ...schemas import CRED
from ...api import SklandAPI
from ...config import config
from ...render import render_ef_card
from ...model import SkUser, Character
from .utils import check_user_character
from ...utils import send_reaction, get_background_image, refresh_cred_token_if_needed, refresh_access_token_if_needed


async def zmdcard_handler(
    user_session: UserSession,
    session: async_scoped_session,
    target: Match[At | int],
    show_all: bool = False,
    is_simple: bool = False,
):
    """终末地森空岛角色卡片"""

    @refresh_cred_token_if_needed
    @refresh_access_token_if_needed
    async def get_character_info(user: SkUser, char: Character):
        return await SklandAPI.endfield_card(CRED(cred=user.cred, token=user.cred_token), user.user_id, char)

    if target.available:
        target_platform_id = target.result.target if isinstance(target.result, At) else target.result
        target_id = (await get_user(user_session.platform, str(target_platform_id))).id
    else:
        target_id = user_session.user_id
    user, ef_characters = await check_user_character(target_id, session)
    send_reaction(user_session, "processing")

    info = await get_character_info(user, ef_characters)
    if not info:
        return
    background = await get_background_image("endfield")
    image = await render_ef_card(info, background, show_all, is_simple)
    if str(background).startswith("http"):
        argot_seg = [Text(str(background)), Image(url=str(background))]
    else:
        argot_seg = Image(path=str(background))
    msg = UniMessage.image(raw=image) + Argot(
        "background", argot_seg, command="background", expired_at=config.argot_expire
    )
    send_reaction(user_session, "done")
    await msg.send(reply_to=True)
    await session.commit()
