"""肉鸽战绩命令"""

import json

from nonebot_plugin_argot import Text, Argot, Image
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_argot.data_source import get_argot
from nonebot.compat import model_dump, type_validate_json
from nonebot_plugin_alconna import At, Match, MsgId, Arparma, UniMessage
from nonebot_plugin_alconna.builtins.extensions import ReplyRecordExtension

from ..api import SklandAPI
from ..config import config
from ..model import SkUser, Character
from ..schemas import CRED, Topics, RogueData
from ..db_handler import get_default_arknights_character
from ..render import render_rogue_card, render_rogue_info
from ..utils import (
    send_reaction,
    get_rogue_background_image,
    refresh_cred_token_if_needed,
    refresh_access_token_if_needed,
)


async def check_user_character(user_id: int, session: async_scoped_session) -> tuple[SkUser, Character]:
    """检查用户和角色绑定状态"""
    user = await session.get(SkUser, user_id)
    if not user:
        await UniMessage("未绑定 skland 账号").finish(at_sender=True)
    char = await get_default_arknights_character(user, session)
    if not char:
        await UniMessage("未绑定 arknights 账号").finish(at_sender=True)
    return user, char


async def rogue_handler(
    user_session: UserSession,
    session: async_scoped_session,
    result: Arparma,
    target: Match[At | int],
):
    """获取明日方舟肉鸽战绩"""

    @refresh_cred_token_if_needed
    @refresh_access_token_if_needed
    async def get_rogue_info(user: SkUser, uid: str, topic_id: str):
        return await SklandAPI.get_rogue(
            CRED(cred=user.cred, token=user.cred_token, userId=str(user.user_id)),
            uid,
            topic_id,
        )

    if target.available:
        target_platform_id = target.result.target if isinstance(target.result, At) else target.result
        target_id = (await get_user(user_session.platform, str(target_platform_id))).id
    else:
        target_id = user_session.user_id

    user, character = await check_user_character(target_id, session)
    send_reaction(user_session, "processing")

    topic_id = Topics(str(result.query("rogue.topic.topic_name"))).topic_id if result.find("rogue.topic") else ""
    rogue = await get_rogue_info(user, str(character.uid), topic_id)
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
        + Argot("data", json.dumps(model_dump(rogue)), command=False)
        + Argot("background", argot_seg, command="background", expired_at=config.argot_expire)
    ).send()
    send_reaction(user_session, "done")
    await session.commit()


async def rginfo_handler(
    id: Match[int],
    msg_id: MsgId,
    ext: ReplyRecordExtension,
    result: Arparma,
    user_session: UserSession,
):
    """获取明日方舟肉鸽战绩详情"""
    if reply := ext.get_reply(msg_id):
        argot = await get_argot("data", reply.id)
        if not argot:
            send_reaction(user_session, "unmatch")
            await UniMessage.text("未找到该暗语或暗语已过期").finish(at_sender=True)
        if data := argot.dump_segment():
            send_reaction(user_session, "processing")
            rogue_data = type_validate_json(RogueData, UniMessage.load(data).extract_plain_text())
            background = await get_rogue_background_image(rogue_data.topic)
            if result.find("rginfo.favored"):
                img = await render_rogue_info(rogue_data, background, id.result, True)
            else:
                img = await render_rogue_info(rogue_data, background, id.result, False)
            if str(background).startswith("http"):
                argot_seg = [Text(str(background)), Image(url=str(background))]
            else:
                argot_seg = Image(path=str(background))
            await UniMessage(
                Image(raw=img) + Argot("background", argot_seg, command="background", expired_at=config.argot_expire)
            ).send()
    else:
        await UniMessage.text("请回复一条肉鸽战绩").finish()
