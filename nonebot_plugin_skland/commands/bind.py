"""Skland account binding commands."""

import asyncio
from typing import Literal
from datetime import datetime, timedelta

from nonebot import logger
from nonebot_plugin_user import UserSession
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_waiter.unimsg import prompt_until
from nonebot_plugin_alconna import Match, Arparma, MsgTarget, UniMessage

from ..services import binding
from ..api import SklandLoginAPI
from ..utils.message import send_reaction
from ..render import render_bound_roles_card
from ..account import exclusive_account_operation
from ..schemas import BoundRolesPlan, BindingAccountSnapshot
from ..utils.qrcode import fetch_user_avatar, render_qrcode_card
from ..exception import (
    LoginException,
    RequestException,
    UnauthorizedException,
    BindingStateChangedError,
    AccountOperationInProgress,
    DuplicateAccountIdentityError,
    AccountIdentityResolutionError,
)


def _card_message(user_session: UserSession, image: bytes, text: str) -> UniMessage:
    message = UniMessage()
    if not user_session.session.scene.is_private:
        message.at(str(user_session.platform_user.id)).text("\n")
    return message.image(raw=image).text(f"\n{text}")


async def _render_plan_card(plan: BoundRolesPlan) -> bytes | None:
    try:
        return await render_bound_roles_card(plan.card)
    except Exception:
        logger.exception("Failed to render the bound-role card")
        return None


async def _send_changed_binding_plan(
    user_session: UserSession,
    plan: BoundRolesPlan,
    text: str,
) -> None:
    image = await _render_plan_card(plan)
    if image is None:
        await UniMessage(text).send(at_sender=True)
        return
    await _card_message(user_session, image, text).send(reply_to=True)


async def _confirm_account_binding(
    *,
    owner_id: int,
    pending: binding.PendingCredential,
    snapshot: BindingAccountSnapshot,
    mode: Literal["add", "update", "upsert"],
    user_session: UserSession,
    session: async_scoped_session,
) -> None:
    try:
        prepared = await binding.prepare_account_binding(owner_id, pending, snapshot, session, mode=mode)
    except AccountIdentityResolutionError:
        await UniMessage("现有账号身份校验失败,请先执行 sk char update 或解绑异常账号").send(at_sender=True)
        return
    except DuplicateAccountIdentityError:
        await UniMessage("检测到重复账号数据,请通过 sk unbind 移除异常项").send(at_sender=True)
        return

    except ValueError as error:
        await UniMessage(str(error)).send(at_sender=True)
        return

    image = await _render_plan_card(prepared.plan)
    if image is None:
        await UniMessage("角色列表渲染失败,未保存账号").send(at_sender=True)
        return

    has_available_roles = any(role.is_available for role in snapshot.roles)
    if prepared.target_account_id is None and not has_available_roles:
        await _card_message(
            user_session,
            image,
            "未找到可绑定的明日方舟或终末地角色,未保存账号",
        ).send(reply_to=True)
        return

    response = await prompt_until(
        _card_message(
            user_session,
            image,
            "请核对角色列表,回复「确认」保存账号,回复「取消」放弃(60 秒)",
        ),
        lambda message: message.extract_plain_text().strip() in {"确认", "取消"},
        timeout=60,
        retry=2,
        retry_prompt="仅接受「确认」或「取消」,请重新回复",
        timeout_prompt="确认超时,未保存账号",
        limited_prompt="确认次数已用尽,未保存账号",
    )
    if response is None:
        return
    if response.extract_plain_text().strip() == "取消":
        await UniMessage("已取消绑定,未保存账号").send(at_sender=True)
        return

    try:
        await binding.commit_account_binding(prepared, session)
    except BindingStateChangedError as error:
        if error.plan is None:
            await UniMessage("绑定数据已变化,请重新确认").send(at_sender=True)
        else:
            await _send_changed_binding_plan(user_session, error.plan, "绑定数据已变化,请重新确认")
        return

    send_reaction(user_session, "done")
    await UniMessage("账号更新成功" if prepared.target_account_id is not None else "绑定成功").send(at_sender=True)


async def bind_handler(
    token: Match[str],
    result: Arparma,
    user_session: UserSession,
    msg_target: MsgTarget,
    session: async_scoped_session,
) -> None:
    owner_id = user_session.user_id
    if not msg_target.private:
        send_reaction(user_session, "unmatch")
        await UniMessage("绑定指令只允许在私聊中使用").send(at_sender=True)
        return
    if not token.available:
        send_reaction(user_session, "unmatch")
        await UniMessage("token 或 cred 错误,请检查格式").send(at_sender=True)
        return

    try:
        async with exclusive_account_operation(owner_id):
            try:
                pending, snapshot = await binding.prepare_binding_candidate(token.result, session)
            except ValueError as error:
                send_reaction(user_session, "unmatch")
                await UniMessage(str(error)).send(at_sender=True)
                return
            except (LoginException, RequestException, UnauthorizedException) as error:
                send_reaction(user_session, "fail")
                await UniMessage(f"绑定失败,错误信息:{error}").send(at_sender=True)
                return
            await _confirm_account_binding(
                owner_id=owner_id,
                pending=pending,
                snapshot=snapshot,
                mode="update" if result.find("bind.update") else "add",
                user_session=user_session,
                session=session,
            )
    except AccountOperationInProgress:
        await UniMessage("已有账号管理操作进行中").send(at_sender=True)


async def qrcode_handler(
    user_session: UserSession,
    session: async_scoped_session,
) -> None:
    owner_id = user_session.user_id
    try:
        async with exclusive_account_operation(owner_id):
            await session.rollback()
            send_reaction(user_session, "processing")
            try:
                avatar = await fetch_user_avatar(user_session.platform_user.avatar)
                scan_id = await SklandLoginAPI.get_scan()
                scan_url = f"hypergryph://scan_login?scanId={scan_id}"
                qr_image = render_qrcode_card(scan_url, avatar)
                message = UniMessage(
                    "请使用森空岛 App 扫描二维码绑定账号\n二维码绑定将由本次命令发起者在角色列表中确认,有效时间约两分钟"
                )
                message += UniMessage.image(raw=qr_image)
                qr_message = await message.send(
                    reply_to=True,
                    at_sender=not user_session.session.scene.is_private,
                )
                end_time = datetime.now() + timedelta(seconds=100)
                scan_code = None
                while datetime.now() < end_time:
                    try:
                        scan_code = await SklandLoginAPI.get_scan_status(scan_id)
                        break
                    except RequestException:
                        pass
                    await asyncio.sleep(2)
                if qr_message.recallable:
                    await qr_message.recall(index=0)
                if not scan_code:
                    send_reaction(user_session, "fail")
                    await UniMessage("二维码超时,请重新获取并扫码").send(at_sender=True)
                    return

                send_reaction(user_session, "received")
                token = await SklandLoginAPI.get_token_by_scan_code(scan_code)
                pending, snapshot = await binding.prepare_binding_candidate(token, session)
            except (LoginException, RequestException, UnauthorizedException) as error:
                send_reaction(user_session, "fail")
                await UniMessage(f"绑定失败,错误信息:{error}").send(at_sender=True)
                return

            await _confirm_account_binding(
                owner_id=owner_id,
                pending=pending,
                snapshot=snapshot,
                mode="upsert",
                user_session=user_session,
                session=session,
            )
    except AccountOperationInProgress:
        await UniMessage("已有账号管理操作进行中").send(at_sender=True)


async def unbind_handler(
    user_session: UserSession,
    session: async_scoped_session,
) -> None:
    owner_id = user_session.user_id
    try:
        async with exclusive_account_operation(owner_id):
            selection_plan = await binding.load_bound_roles_plan(
                owner_id,
                session,
                mode="unbind_selection",
            )
            if not selection_plan.card.accounts:
                send_reaction(user_session, "unmatch")
                await UniMessage("你还没有绑定森空岛账号").send(at_sender=True)
                return
            selection_image = await _render_plan_card(selection_plan)
            if selection_image is None:
                await UniMessage("角色列表渲染失败,未做任何更改").send(at_sender=True)
                return

            valid_indexes = {str(account.index) for account in selection_plan.card.accounts}
            response = await prompt_until(
                _card_message(
                    user_session,
                    selection_image,
                    "请回复账号序号,或回复「全部」「取消」(60 秒)",
                ),
                lambda message: message.extract_plain_text().strip() in valid_indexes | {"全部", "取消"},
                timeout=60,
                retry=2,
                retry_prompt="账号序号无效,请回复卡片中的账号序号、「全部」或「取消」",
                timeout_prompt="解绑选择超时,未做任何更改",
                limited_prompt="账号序号输入次数已用尽,未做任何更改",
            )
            if response is None:
                return
            selection = response.extract_plain_text().strip()
            if selection == "取消":
                await UniMessage("已取消解绑操作").send(at_sender=True)
                return
            if selection == "全部":
                selected_account_ids = {
                    account.account_id for account in selection_plan.card.accounts if account.account_id is not None
                }
            else:
                selected_account_ids = {
                    account.account_id
                    for account in selection_plan.card.accounts
                    if account.index == int(selection) and account.account_id is not None
                }

            try:
                prepared = await binding.prepare_account_unbind(owner_id, selected_account_ids, session)
            except BindingStateChangedError:
                await UniMessage("绑定数据已变化,请重新操作").send(at_sender=True)
                return
            confirmation_image = await _render_plan_card(prepared.plan)
            if confirmation_image is None:
                await UniMessage("角色列表渲染失败,未做任何更改").send(at_sender=True)
                return

            confirmation_text = (
                "确认解绑全部账号将删除所有角色和抽卡记录,回复「确认」继续(30 秒)"
                if selection == "全部"
                else "确认解绑将删除所选账号的角色和抽卡记录,回复「确认」继续(30 秒)"
            )
            confirmation = await prompt_until(
                _card_message(user_session, confirmation_image, confirmation_text),
                lambda _message: True,
                timeout=30,
                retry=0,
                timeout_prompt="解绑确认超时,未做任何更改",
            )
            if confirmation is None:
                return
            if confirmation.extract_plain_text().strip() != "确认":
                await UniMessage("已取消解绑操作").send(at_sender=True)
                return

            try:
                await binding.commit_account_unbind(prepared, session)
            except BindingStateChangedError as error:
                if error.plan is None:
                    await UniMessage("绑定数据已变化,请重新操作").send(at_sender=True)
                else:
                    await _send_changed_binding_plan(user_session, error.plan, "绑定数据已变化,请重新操作")
                return

            overview = await binding.load_bound_roles_plan(
                owner_id,
                session,
                mode="overview",
            )
            send_reaction(user_session, "done")
            if not overview.card.accounts:
                await UniMessage("解绑成功,已清除全部绑定数据").send(at_sender=True)
                return
            await _send_changed_binding_plan(user_session, overview, "解绑成功")
    except AccountOperationInProgress:
        await UniMessage("已有账号管理操作进行中").send(at_sender=True)
