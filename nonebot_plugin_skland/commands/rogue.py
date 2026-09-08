"""肉鸽战绩命令"""

import json

from nonebot_plugin_argot import Text, Argot, Image
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_argot.data_source import get_argot
from nonebot.compat import model_dump, type_validate_json
from nonebot_plugin_alconna import At, Match, MsgId, Arparma, UniMessage
from nonebot_plugin_alconna.builtins.extensions import ReplyRecordExtension

from ..model import SkUser
from ..api import SklandAPI
from ..config import config
from ..exception import SklandException
from .selection import check_user_character
from ..schemas import CRED, Topics, RogueData
from ..services.auth import refresh_credentials
from ..render import render_rogue_card, render_rogue_info
from ..utils.background import get_rogue_background_image
from ..utils.message import send_reaction, send_request_error


@refresh_credentials
async def _get_rogue_data(user: SkUser, uid: str, topic_id: str):
    return await SklandAPI.get_rogue(
        CRED(cred=user.cred, token=user.cred_token, userId=user.skland_user_id),
        uid,
        topic_id,
    )


async def rogue_handler(
    user_session: UserSession,
    session: async_scoped_session,
    result: Arparma,
    target: Match[At | int],
    *,
    role_index: int | None = None,
):
    """获取明日方舟肉鸽战绩"""

    if target.available:
        target_platform_id = target.result.target if isinstance(target.result, At) else target.result
        target_id = (await get_user(user_session.platform, str(target_platform_id))).id
    else:
        target_id = user_session.user_id

    selected = await check_user_character(target_id, user_session, session, app_code="arknights", role_index=role_index)
    if selected is None:
        return
    user, character = selected
    if not user.skland_user_id:
        await session.rollback()
        await UniMessage("账号身份尚未同步,请先执行 sk char update").send(at_sender=True)
        return
    send_reaction(user_session, "processing")

    topic_id = Topics(str(result.query("rogue.topic.topic_name"))).topic_id if result.find("rogue.topic") else ""
    try:
        rogue = await _get_rogue_data(user, str(character.uid), topic_id)
    except SklandException as error:
        await session.commit()
        await send_request_error(error)
        return
    await session.commit()
    if not rogue:
        return
    background = await get_rogue_background_image(topic_id)
    img = await render_rogue_card(rogue, background)
    if str(background).startswith("http"):
        argot_seg = [Text(str(background)), Image(url=str(background))]
    else:
        argot_seg = Image(path=str(background))
    await UniMessage(
        Image(raw=img)
        + Argot("data", json.dumps(model_dump(rogue)), command=False, expired_at=config.argot_expire)
        + Argot("background", argot_seg, command="background", expired_at=config.argot_expire)
    ).send()
    send_reaction(user_session, "done")


async def rginfo_handler(
    id: Match[int],
    msg_id: MsgId,
    ext: ReplyRecordExtension,
    result: Arparma,
    user_session: UserSession,
    session: async_scoped_session,
    *,
    role_index: int | None = None,
):
    """Show cached rogue details or query an explicitly selected role."""
    owner_id = user_session.user_id
    rogue_data: RogueData | None = None
    if reply := ext.get_reply(msg_id):
        argot = await get_argot("data", reply.id)
        if not argot or not (data := argot.dump_segment()):
            await session.rollback()
            send_reaction(user_session, "unmatch")
            await UniMessage.text("未找到该暗语或暗语已过期").finish(at_sender=True)
        rogue_data = type_validate_json(RogueData, UniMessage.load(data).extract_plain_text())

    if role_index is not None:
        selected = await check_user_character(
            owner_id, user_session, session, app_code="arknights", role_index=role_index
        )
        if selected is None:
            return
        user, character = selected
        if not user.skland_user_id:
            await session.rollback()
            await UniMessage("账号身份尚未同步,请先执行 sk char update").send(at_sender=True)
            return
        try:
            rogue_data = await _get_rogue_data(user, character.uid, rogue_data.topic if rogue_data is not None else "")
        except SklandException as error:
            await session.commit()
            await send_request_error(error)
            return
        await session.commit()
        if rogue_data is None:
            return
    else:
        await session.rollback()
        if rogue_data is None:
            await UniMessage.text("请回复一条肉鸽战绩，或使用 -r 指定自己的角色").finish()

    send_reaction(user_session, "processing")
    background = await get_rogue_background_image(rogue_data.topic)
    img = await render_rogue_info(rogue_data, background, id.result, result.find("rginfo.favored"))
    if str(background).startswith("http"):
        argot_seg = [Text(str(background)), Image(url=str(background))]
    else:
        argot_seg = Image(path=str(background))
    await UniMessage(
        Image(raw=img) + Argot("background", argot_seg, command="background", expired_at=config.argot_expire)
    ).send()
