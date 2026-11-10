"""Optional QQ official account buttons; other adapters do not import the QQ SDK."""

import asyncio
import secrets
from dataclasses import dataclass

from nonebot import logger, on_notice
from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna import UniMessage
from nonebot.matcher import current_bot, current_event

from ..schemas import BoundRolesPlan


def current_context() -> tuple[Bot, Event] | None:
    bot, event = current_bot.get(None), current_event.get(None)
    if bot is None or event is None or bot.adapter.get_name() != "QQ":
        return None
    from nonebot.adapters.qq import Bot as QQBot
    from nonebot.adapters.qq.event import C2CMessageCreateEvent, GroupMessageCreateEvent

    if (
        isinstance(bot, QQBot)
        and bot.bot_info.intent.interaction
        and isinstance(event, (GroupMessageCreateEvent, C2CMessageCreateEvent))
    ):
        return bot, event
    return None


@dataclass
class _ButtonRequest:
    bot_id: str
    user_id: str
    session_id: str
    deadline: float
    future: asyncio.Future[str]
    actions: frozenset[str] = frozenset({"confirm", "cancel"})
    event: Event | None = None
    claimed: bool = False


_pending: dict[str, _ButtonRequest] = {}


def _is_account_button(bot: Bot, event: Event) -> bool:
    if bot.adapter.get_name() != "QQ":
        return False
    from nonebot.adapters.qq.event import InteractionCreateEvent

    return (
        isinstance(event, InteractionCreateEvent)
        and event.type == 11
        and (event.data.resolved.button_data or "").startswith("skbind:")
    )


_account_button_click = on_notice(rule=_is_account_button, priority=0, block=True)


@_account_button_click.handle()
async def _handle_account_button(bot: Bot, event: Event) -> None:
    from nonebot.adapters.qq import Bot as QQBot
    from nonebot.adapters.qq.event import InteractionCreateEvent

    assert isinstance(bot, QQBot)
    assert isinstance(event, InteractionCreateEvent)
    parts = (event.data.resolved.button_data or "").split(":")
    request = _pending.get(parts[1]) if len(parts) == 3 else None
    valid = (
        request is not None
        and parts[2] in request.actions
        and not request.claimed
        and not request.future.done()
        and asyncio.get_running_loop().time() < request.deadline
        and bot.self_id == request.bot_id
        and event.get_user_id() == request.user_id
        and event.get_session_id() == request.session_id
    )
    if not valid:
        await bot.put_interaction(interaction_id=event.id, code=1)
        return

    assert request is not None
    # Claim before acknowledging: simultaneous clicks must not confirm twice.
    request.claimed = True
    try:
        await asyncio.wait_for(bot.put_interaction(interaction_id=event.id, code=0), timeout=3)
    except Exception:
        request.claimed = False
        logger.warning("Failed to acknowledge the account button")
        return
    if not request.future.done() and asyncio.get_running_loop().time() < request.deadline:
        request.event = event
        request.future.set_result(parts[2])


async def prompt_buttons(
    image: bytes | None,
    bot: Bot,
    event: Event,
    *,
    text: str,
    options: list[tuple[str, str, int]],
    timeout: float,
    timeout_prompt: str,
    failure_prompt: str,
) -> tuple[str, Event] | None:
    from nonebot.adapters.qq import MessageSegment as QQSegment
    from nonebot.adapters.qq.models import (
        Action,
        Button,
        Permission,
        RenderData,
        InlineKeyboard,
        MessageKeyboard,
        InlineKeyboardRow,
    )

    if image is not None:
        await UniMessage.image(raw=image).send(reply_to=False)
    loop = asyncio.get_running_loop()
    nonce = secrets.token_urlsafe(18)
    request = _ButtonRequest(
        bot_id=bot.self_id,
        user_id=event.get_user_id(),
        session_id=event.get_session_id(),
        deadline=loop.time() + timeout,
        future=loop.create_future(),
        actions=frozenset(action for action, _, _ in options),
    )
    _pending[nonce] = request
    buttons = [
        Button(
            id=action,
            render_data=RenderData(label=label, visited_label=label, style=style),
            action=Action(
                type=1,
                permission=Permission(type=0, specify_user_ids=[request.user_id]),
                data=f"skbind:{nonce}:{action}",
            ),
        )
        for action, label, style in options
    ]
    keyboard = MessageKeyboard(
        content=InlineKeyboard(
            rows=[InlineKeyboardRow(buttons=buttons[start : start + 5]) for start in range(0, len(buttons), 5)]
        )
    )
    try:
        try:
            await bot.send(
                event,
                QQSegment.markdown(text) + QQSegment.keyboard(keyboard),
            )
        except Exception as error:
            code = getattr(error, "code", None)
            logger.error(
                "Failed to send the account buttons: type={} status={} code={} detail={} trace_id={} reply_seq={}",
                type(error).__name__,
                getattr(error, "status_code", None),
                code,
                getattr(error, "message", None) or str(error),
                getattr(error, "trace_id", None),
                getattr(event, "_reply_seq", None),
            )
            reason = f"QQ错误码 {code}" if code is not None else type(error).__name__
            await UniMessage(failure_prompt.format(reason=reason) + ",请联系管理员排查").send(at_sender=True)
            return None
        try:
            choice = await asyncio.wait_for(request.future, timeout=max(0, request.deadline - loop.time()))
        except asyncio.TimeoutError:
            await UniMessage(timeout_prompt).send(at_sender=True)
            return None
        assert request.event is not None
        return choice, request.event
    finally:
        _pending.pop(nonce, None)
        if not request.future.done():
            request.future.cancel()


async def confirm_binding(image: bytes, bot: Bot, event: Event) -> UniMessage | None:
    response = await prompt_buttons(
        image,
        bot,
        event,
        text="请核对上方角色列表，再点击按钮确认或取消（60 秒内有效，仅本次发起者可操作）。",
        options=[("confirm", "确认绑定", 1), ("cancel", "取消", 0)],
        timeout=60,
        timeout_prompt="确认超时,未保存账号,请重新扫码绑定",
        failure_prompt="确认按钮发送失败（{reason}）,未保存账号",
    )
    if response is None:
        return None
    return UniMessage("确认" if response[0] == "confirm" else "取消")


async def select_unbind_account(
    plan: BoundRolesPlan,
    image: bytes | None,
    bot: Bot,
    event: Event,
) -> UniMessage | None:
    accounts = plan.card.accounts
    pages = (len(accounts) + 19) // 20
    page = 0
    reply_event = event
    deadline = asyncio.get_running_loop().time() + 60
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            await UniMessage("解绑选择超时,未做任何更改").send(at_sender=True)
            return None
        options = [
            (str(account.index), f"账号 {account.index}", 1) for account in accounts[page * 20 : (page + 1) * 20]
        ]
        if page > 0:
            options.append(("prev", "上一页", 0))
        if page + 1 < pages:
            options.append(("next", "下一页", 0))
        options.extend([("all", "全部", 0), ("cancel", "取消", 0)])
        response = await prompt_buttons(
            image,
            bot,
            reply_event,
            text=f"请对照上方角色列表选择要解绑的账号，或选择全部／取消。"
            f"仅本次发起者可操作（60 秒内有效，第 {page + 1}/{pages} 页）。",
            options=options,
            timeout=remaining,
            timeout_prompt="解绑选择超时,未做任何更改",
            failure_prompt="解绑选择按钮发送失败（{reason}）,未做任何更改",
        )
        if response is None:
            return None
        choice, reply_event = response
        if choice in {"prev", "next"}:
            page += 1 if choice == "next" else -1
            image = None
            continue
        return UniMessage({"all": "全部", "cancel": "取消"}.get(choice, choice))
