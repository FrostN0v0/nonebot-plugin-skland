"""绑定相关命令"""

import asyncio
from io import BytesIO
from datetime import datetime, timedelta

import qrcode
from nonebot_plugin_user import UserSession
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_alconna import Match, Arparma, MsgTarget, UniMessage

from ..model import SkUser
from ..schemas import CRED
from ..exception import RequestException
from ..api import SklandAPI, SklandLoginAPI
from ..utils import send_reaction, get_characters_and_bind


async def bind_handler(
    token: Match[str],
    result: Arparma,
    user_session: UserSession,
    msg_target: MsgTarget,
    session: async_scoped_session,
):
    """绑定森空岛账号"""

    if not msg_target.private:
        send_reaction(user_session, "unmatch")
        await UniMessage("绑定指令只允许在私聊中使用").finish(at_sender=True)

    if user := await session.get(SkUser, user_session.user_id):
        if result.find("bind.update"):
            if len(token.result) == 24:
                grant_code = await SklandLoginAPI.get_grant_code(token.result, 0)
                cred = await SklandLoginAPI.get_cred(grant_code)
                user.access_token = token.result
                user.cred = cred.cred
                user.cred_token = cred.token
            elif len(token.result) == 32:
                cred_token = await SklandLoginAPI.refresh_token(token.result)
                user.cred = token.result
                user.cred_token = cred_token
            else:
                send_reaction(user_session, "unmatch")
                await UniMessage("token 或 cred 错误,请检查格式").finish(at_sender=True)
            await get_characters_and_bind(user, session)
            send_reaction(user_session, "done")
            await UniMessage("更新成功").finish(at_sender=True)
        send_reaction(user_session, "unmatch")
        await UniMessage("已绑定过 skland 账号").finish(at_sender=True)

    if token.available:
        try:
            if len(token.result) == 24:
                grant_code = await SklandLoginAPI.get_grant_code(token.result, 0)
                cred = await SklandLoginAPI.get_cred(grant_code)
                user = SkUser(
                    access_token=token.result,
                    cred=cred.cred,
                    cred_token=cred.token,
                    id=user_session.user_id,
                    user_id=cred.userId,
                )
            elif len(token.result) == 32:
                cred_token = await SklandLoginAPI.refresh_token(token.result)
                user_id = await SklandAPI.get_user_ID(CRED(cred=token.result, token=cred_token))
                user = SkUser(
                    cred=token.result,
                    cred_token=cred_token,
                    id=user_session.user_id,
                    user_id=user_id,
                )
            else:
                send_reaction(user_session, "unmatch")
                await UniMessage("token 或 cred 错误,请检查格式").finish(at_sender=True)
            session.add(user)
            await get_characters_and_bind(user, session)
            send_reaction(user_session, "done")
            await UniMessage("绑定成功").finish(at_sender=True)
        except RequestException as e:
            send_reaction(user_session, "fail")
            await UniMessage(f"绑定失败,错误信息:{e}").finish(at_sender=True)


async def qrcode_handler(
    user_session: UserSession,
    session: async_scoped_session,
):
    """二维码绑定森空岛账号"""
    send_reaction(user_session, "processing")
    scan_id = await SklandLoginAPI.get_scan()
    scan_url = f"hypergryph://scan_login?scanId={scan_id}"
    qr_code = qrcode.make(scan_url)
    result_stream = BytesIO()
    qr_code.save(result_stream, "PNG")
    msg = UniMessage("请使用森空岛app扫描二维码绑定账号\n二维码有效时间两分钟，请不要扫描他人的登录二维码进行绑定~")
    msg += UniMessage.image(raw=result_stream.getvalue())
    qr_msg = await msg.send(reply_to=True)
    end_time = datetime.now() + timedelta(seconds=100)
    scan_code = None
    while datetime.now() < end_time:
        try:
            scan_code = await SklandLoginAPI.get_scan_status(scan_id)
            break
        except RequestException:
            pass
        await asyncio.sleep(2)
    if qr_msg.recallable:
        await qr_msg.recall(index=0)
    if scan_code:
        send_reaction(user_session, "received")
        token = await SklandLoginAPI.get_token_by_scan_code(scan_code)
        grant_code = await SklandLoginAPI.get_grant_code(token, 0)
        cred = await SklandLoginAPI.get_cred(grant_code)
        if user := await session.get(SkUser, user_session.user_id):
            user.access_token = token
            user.cred = cred.cred
            user.cred_token = cred.token
        else:
            user = SkUser(
                access_token=token,
                cred=cred.cred,
                cred_token=cred.token,
                id=user_session.user_id,
                user_id=cred.userId,
            )
            session.add(user)
        await get_characters_and_bind(user, session)
        send_reaction(user_session, "done")
        await UniMessage("绑定成功").finish(at_sender=True)
    else:
        send_reaction(user_session, "fail")
        await UniMessage("二维码超时,请重新获取并扫码").finish(at_sender=True)
