"""终末地签到命令"""

import json
from datetime import datetime

from nonebot.adapters import Bot
from nonebot.params import Depends
from nonebot.compat import model_dump
from nonebot.permission import SuperUser
from nonebot_plugin_user import UserSession
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_alconna import Match, Arparma, CustomNode, UniMessage

from ...model import SkUser
from ...api import SklandAPI
from ...config import CACHE_DIR
from ...schemas import CRED, EndfieldSignResponse
from ...db_handler import (
    select_all_users,
    get_endfield_characters,
    get_endfield_character_by_uid,
    get_default_endfield_character,
)
from ...utils import (
    send_reaction,
    format_endfield_sign_result,
    refresh_cred_token_if_needed,
    refresh_access_token_if_needed,
    refresh_cred_token_with_error_return,
    refresh_access_token_with_error_return,
)


async def zmdsign_sign_handler(
    user_session: UserSession,
    session: async_scoped_session,
    uid: Match[str],
    result: Arparma,
):
    """终末地森空岛签到"""

    @refresh_cred_token_if_needed
    @refresh_access_token_if_needed
    async def sign_in(user: SkUser, uid: str, server_id: str):
        """执行签到逻辑"""
        cred = CRED(cred=user.cred, token=user.cred_token)
        return await SklandAPI.endfield_sign(cred, uid, server_id=server_id)

    user = await session.get(SkUser, user_session.user_id)
    if not user:
        send_reaction(user_session, "unmatch")
        await UniMessage("未绑定 skland 账号").finish(at_sender=True)

    if uid.available:
        chars = [await get_endfield_character_by_uid(user, uid.result, session)]
    elif result.find("zmdsign.sign.all"):
        chars = await get_endfield_characters(user, session)
    elif character := await get_default_endfield_character(user, session):
        chars = [character]
    else:
        send_reaction(user_session, "unmatch")
        await UniMessage("未绑定 endfield 账号").finish(at_sender=True)

    sign_result: dict[str, EndfieldSignResponse] = {}
    for character in chars:
        if res := await sign_in(user, str(character.uid), character.channel_master_id):
            sign_result[character.nickname] = res

    if sign_result:
        send_reaction(user_session, "done")
        await UniMessage(
            "\n".join(
                f"角色: {nickname} 签到成功，获得了:\n" + sign.award_summary for nickname, sign in sign_result.items()
            )
        ).send(at_sender=True)

    await session.commit()


@refresh_cred_token_with_error_return
@refresh_access_token_with_error_return
async def endfield_sign_in(user: SkUser, uid: str, server_id: str) -> EndfieldSignResponse:
    """执行终末地签到逻辑（带错误返回）"""
    cred = CRED(cred=user.cred, token=user.cred_token)
    return await SklandAPI.endfield_sign(cred, uid, server_id=server_id)


async def zmdsign_status_handler(
    user_session: UserSession,
    session: async_scoped_session,
    bot: Bot,
    result: Arparma | bool,
    is_superuser: bool = Depends(SuperUser()),
):
    """查看终末地签到状态"""
    sign_result_file = CACHE_DIR / "endfield_sign_result.json"
    sign_result = {}
    sign_data = {}
    if not sign_result_file.exists():
        await UniMessage.text("未找到签到结果").finish()
    else:
        with open(sign_result_file, encoding="utf-8") as f:
            sign_result = json.load(f)
    sign_data = sign_result.get("data", {})
    sign_time = sign_result.get("timestamp", "未记录签到时间")
    if isinstance(result, Arparma) and result.find("zmdsign.status.all"):
        if not is_superuser:
            await UniMessage.text("该指令仅超管可用").finish()
    elif isinstance(result, bool) and result:
        if not is_superuser:
            await UniMessage.text("该指令仅超管可用").finish()
    else:
        user = await session.get(SkUser, user_session.user_id)
        if not user:
            await UniMessage("未绑定 skland 账号").finish(at_sender=True)
        chars = await get_endfield_characters(user, session)
        char_nicknames = {char.nickname for char in chars}
        sign_data = {nickname: value for nickname, value in sign_data.items() if nickname in char_nicknames}
    send_reaction(user_session, "processing")
    if user_session.platform == "QQClient":
        sliced_nodes: list[dict[str, str]] = []
        prased_sign_result = format_endfield_sign_result(sign_data, sign_time, False)
        NODE_SLICE_LIMIT = 98
        formatted_nodes = {k: f"{v}\n" for k, v in prased_sign_result.results.items()}
        for i in range(0, len(formatted_nodes.items()), NODE_SLICE_LIMIT):
            sliced_node_items = list(formatted_nodes.items())[i : i + NODE_SLICE_LIMIT]
            sliced_nodes.append(dict(sliced_node_items))
        for index, node in enumerate(sliced_nodes):
            if index == 0:
                await UniMessage.reference(
                    CustomNode(bot.self_id, "签到结果", prased_sign_result.summary),
                    *[CustomNode(bot.self_id, nickname, content) for nickname, content in node.items()],
                ).send()
            else:
                await UniMessage.reference(
                    *[CustomNode(bot.self_id, nickname, content) for nickname, content in node.items()],
                ).send()
        send_reaction(user_session, "done")
    else:
        prased_sign_result = format_endfield_sign_result(sign_data, sign_time, True)
        formatted_messages = [prased_sign_result.results[nickname] for nickname in prased_sign_result.results]
        send_reaction(user_session, "done")
        await UniMessage.text(prased_sign_result.summary + "\n".join(formatted_messages)).finish()


async def zmdsign_all_handler(
    user_session: UserSession,
    session: async_scoped_session,
    bot: Bot,
    is_superuser: bool = Depends(SuperUser()),
):
    """签到所有终末地绑定角色"""
    if not is_superuser:
        await UniMessage.text("该指令仅超管可用").finish()
    send_reaction(user_session, "processing")
    sign_result: dict[str, EndfieldSignResponse | str] = {}
    serializable_sign_result: dict[str, dict | str] = {}
    for user in await select_all_users(session):
        characters = await get_endfield_characters(user, session)
        for character in characters:
            sign_result[character.nickname] = await endfield_sign_in(
                user, str(character.uid), character.channel_master_id
            )
    serializable_sign_result["data"] = {
        nickname: model_dump(res) if isinstance(res, EndfieldSignResponse) else res
        for nickname, res in sign_result.items()
    }
    serializable_sign_result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    sign_result_file = CACHE_DIR / "endfield_sign_result.json"
    if not sign_result_file.exists():
        sign_result_file.parent.mkdir(parents=True, exist_ok=True)
    with open(sign_result_file, "w", encoding="utf-8") as f:
        json.dump(serializable_sign_result, f, ensure_ascii=False, indent=2)
    await zmdsign_status_handler(user_session, session, bot, True, is_superuser=is_superuser)
