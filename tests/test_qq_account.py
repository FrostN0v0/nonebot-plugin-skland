import asyncio
import builtins
import importlib.util
from unittest.mock import patch
from types import SimpleNamespace
from contextlib import contextmanager

import pytest
from sqlalchemy import select
from nonebot.adapters.qq import Bot, Adapter
from nonebot.adapters.qq.config import BotInfo
from nonebot.matcher import current_bot, current_event
from nonebot.adapters.qq.event import C2CMessageCreateEvent, InteractionCreateEvent, GroupAtMessageCreateEvent

STAMP = "2026-01-01T00:00:00+00:00"


def _message(*, user="owner", group="group-a", private=False):
    common = {"id": "command-id", "content": "/sk unbind", "timestamp": STAMP}
    if private:
        return C2CMessageCreateEvent(**common, author={"id": user, "user_openid": user})
    return GroupAtMessageCreateEvent(
        **common,
        group_id=group,
        group_openid=group,
        author={"id": user, "bot": False, "member_openid": user, "member_role": "member"},
    )


def _click(nonce, action="confirm", *, user="owner", group="group-a", private=False):
    return InteractionCreateEvent(
        id=f"click-{nonce}-{action}",
        event_id=f"outer-{nonce}-{action}",
        type=11,
        version=1,
        timestamp=STAMP,
        scene="c2c" if private else "group",
        chat_type=2 if private else 1,
        application_id="test-bot",
        user_openid=user if private else None,
        group_openid=None if private else group,
        group_member_openid=None if private else user,
        data={"resolved": {"button_data": f"skbind:{nonce}:{action}"}},
    )


@contextmanager
def _context(bot, event):
    bot_token, event_token = current_bot.set(bot), current_event.set(event)
    try:
        yield
    finally:
        current_event.reset(event_token)
        current_bot.reset(bot_token)


@pytest.fixture
def qq(app, mocker):
    import nonebot
    from nonebot_plugin_alconna import UniMessage

    from nonebot_plugin_skland.integrations import qq_account

    bot = Bot(
        Adapter(nonebot.get_driver()),
        "test-bot",
        BotInfo(id="test-bot", secret="test-secret", intent={"interaction": True}),
    )
    calls = []

    async def send(message, **kwargs):
        calls.append((kwargs.get("target") or current_event.get(), message.extract_plain_text(), kwargs))

    mocker.patch.object(UniMessage, "send", new=send)
    native_send = mocker.patch.object(bot, "send", new=mocker.AsyncMock())
    ack = mocker.patch.object(bot, "put_interaction", new=mocker.AsyncMock())
    yield SimpleNamespace(bot=bot, native_send=native_send, ack=ack, calls=calls, module=qq_account)
    assert not qq_account._pending


async def _wait_for_send(qq, count):
    for _ in range(100):
        await asyncio.sleep(0.01)
        if qq.native_send.await_count >= count:
            return
    pytest.fail("Expected QQ button message was not sent")


@pytest.mark.asyncio
async def test_account_button_rule_uses_real_nonebot_dispatch(qq):
    matcher = qq.module._account_button_click
    assert await matcher.check_rule(qq.bot, _click("dispatch-check"), {"has_state": True})
    assert not await matcher.check_rule(qq.bot, _message(), {})


@pytest.mark.parametrize("private", [False, True], ids=["group", "c2c"])
@pytest.mark.asyncio
async def test_account_reply_sequences_and_callback_event_id(qq, mocker, private):
    event = _message(private=private)
    send = mocker.patch.object(qq.bot, "send_to_c2c" if private else "send_to_group", new=mocker.AsyncMock())
    for index in range(4):
        await Bot.send(qq.bot, event, "synthetic response")
        assert send.await_args.kwargs["msg_seq"] == index + 1
        assert send.await_args.kwargs["msg_id"] == event.id
    clicked = _click("callback-check", private=private)
    await Bot.send(qq.bot, clicked, "synthetic result")
    assert send.await_args.kwargs["event_id"] == clicked.event_id
    assert "msg_id" not in send.await_args.kwargs


def test_optional_sdk_and_intent_gate(qq, mocker):
    module = qq.module
    with _context(qq.bot, _message()):
        assert module.current_context() is not None
        qq.bot.bot_info.intent.interaction = False
        assert module.current_context() is None

    original_import = builtins.__import__

    def without_qq(name, *args, **kwargs):
        if name.startswith("nonebot.adapters.qq"):
            raise ModuleNotFoundError(name)
        return original_import(name, *args, **kwargs)

    spec = importlib.util.spec_from_file_location(
        "nonebot_plugin_skland.integrations.qq_account_without_sdk", module.__file__
    )
    isolated = importlib.util.module_from_spec(spec)
    mocker.patch.dict("sys.modules", {spec.name: isolated})
    with patch("builtins.__import__", side_effect=without_qq):
        spec.loader.exec_module(isolated)
        other_bot = SimpleNamespace(adapter=SimpleNamespace(get_name=lambda: "OneBot V11"))
        with _context(other_bot, _message()):
            assert isolated.current_context() is None


@pytest.mark.parametrize("private", [False, True], ids=["group", "c2c"])
@pytest.mark.asyncio
async def test_binding_buttons_validate_actor_and_reply_once(qq, private):
    module = qq.module
    event = _message(private=private)
    with _context(qq.bot, event):
        task = asyncio.create_task(module.confirm_binding(b"card", qq.bot, event))
        await _wait_for_send(qq, 1)
        nonce, request = next(iter(module._pending.items()))
        message = qq.native_send.await_args.args[1]
        keyboard = message["keyboard"][0].data["keyboard"].content
        assert keyboard is not None
        assert keyboard.rows is not None
        buttons = keyboard.rows[0].buttons
        assert buttons is not None
        assert [button.render_data.label for button in buttons] == ["确认绑定", "取消"]
        assert all(button.group_id is None for button in buttons)
        assert all(button.action.type == 1 for button in buttons)
        assert all(button.action.permission.specify_user_ids == ["owner"] for button in buttons)

        for bad in (
            _click(nonce, user="other", private=private),
            _click("unknown", private=private),
            _click(nonce, action="all", private=private),
        ):
            await module._handle_account_button(qq.bot, bad)
            assert qq.ack.await_args.kwargs["code"] == 1
            assert not request.future.done()
        if not private:
            await module._handle_account_button(qq.bot, _click(nonce, group="group-b"))
            assert qq.ack.await_args.kwargs["code"] == 1
            assert not request.future.done()
        deadline = request.deadline
        request.deadline = 0
        await module._handle_account_button(qq.bot, _click(nonce, private=private))
        assert not request.future.done()
        request.deadline = deadline

        gate = asyncio.Event()

        async def acknowledge(*, interaction_id, code):
            if code == 0:
                await gate.wait()

        qq.ack.side_effect = acknowledge
        clicked = _click(nonce, private=private)
        first = asyncio.create_task(module._handle_account_button(qq.bot, clicked))
        for _ in range(100):
            await asyncio.sleep(0)
            if request.claimed:
                break
        await module._handle_account_button(qq.bot, _click(nonce, "cancel", private=private))
        assert qq.ack.await_args.kwargs["code"] == 1
        gate.set()
        await first
        response = await task
        assert response.extract_plain_text() == "确认"
        await module._handle_account_button(qq.bot, clicked)
        assert qq.ack.await_args.kwargs["code"] == 1


@pytest.mark.asyncio
async def test_binding_button_ack_send_timeout_and_cancellation(qq):
    module = qq.module
    event = _message()
    with _context(qq.bot, event):
        task = asyncio.create_task(module.confirm_binding(b"card", qq.bot, event))
        await _wait_for_send(qq, 1)
        nonce, request = next(iter(module._pending.items()))
        qq.ack.side_effect = RuntimeError("simulated acknowledgement failure")
        await module._handle_account_button(qq.bot, _click(nonce))
        assert not request.future.done()
        assert not request.claimed
        qq.ack.side_effect = None
        await module._handle_account_button(qq.bot, _click(nonce, "cancel"))
        assert (await task).extract_plain_text() == "取消"

        qq.native_send.side_effect = RuntimeError("simulated send failure")
        assert await module.confirm_binding(b"card", qq.bot, event) is None
        assert "RuntimeError" in qq.calls[-1][1]
        qq.native_send.side_effect = None

        assert (
            await module.prompt_buttons(
                None,
                qq.bot,
                event,
                text="confirm",
                options=[("confirm", "确认", 1)],
                timeout=0,
                timeout_prompt="确认超时",
                failure_prompt="发送失败（{reason}）",
            )
            is None
        )
        assert qq.calls[-1][1] == "确认超时"

        previous = qq.native_send.await_count
        task = asyncio.create_task(module.confirm_binding(b"card", qq.bot, event))
        await _wait_for_send(qq, previous + 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_account_pages_reject_previous_page_and_keep_keyboard_limits(qq):
    module = qq.module
    plan = SimpleNamespace(card=SimpleNamespace(accounts=[SimpleNamespace(index=index) for index in range(1, 42)]))
    event = _message()
    with _context(qq.bot, event):
        task = asyncio.create_task(module.select_unbind_account(plan, b"card", qq.bot, event))
        await _wait_for_send(qq, 1)
        for page, action in enumerate(("next", "next", "41"), 1):
            nonce = next(iter(module._pending))
            rows = qq.native_send.await_args.args[1]["keyboard"][0].data["keyboard"].content.rows
            assert len(rows) <= 5
            assert all(len(row.buttons) <= 5 for row in rows)
            await module._handle_account_button(qq.bot, _click(nonce, action))
            if action == "41":
                break
            await _wait_for_send(qq, page + 1)
            await module._handle_account_button(qq.bot, _click(nonce, "all"))
            assert qq.ack.await_args.kwargs["code"] == 1
        assert (await task).extract_plain_text() == "41"


@pytest.mark.parametrize(
    ("selection", "confirm", "remaining"),
    [("1", "confirm", 1), ("all", "confirm", 0), ("all", "cancel", 2), ("cancel", None, 2)],
)
@pytest.mark.asyncio
async def test_unbind_buttons_preserve_database_contract(qq, mocker, make_user_session, selection, confirm, remaining):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.model import SkUser
    from nonebot_plugin_skland.commands import bind

    mocker.patch.object(bind, "render_bound_roles_card", new=mocker.AsyncMock(return_value=b"card"))
    mocker.patch.object(bind, "send_reaction")
    waiter = mocker.patch.object(bind, "prompt_until", new=mocker.AsyncMock())
    async with get_session() as session:
        session.add_all(
            [
                SkUser(
                    owner_id=701,
                    access_token="synthetic",
                    cred="synthetic",
                    cred_token="synthetic",
                    skland_user_id=f"remote-{index}",
                )
                for index in (1, 2)
            ]
        )
        await session.commit()
        user_session = await make_user_session(session, 701)
        event = _message(user="701")
        with _context(qq.bot, event):
            task = asyncio.create_task(bind.unbind_handler(user_session, session))
            await _wait_for_send(qq, 1)
            await qq.module._handle_account_button(
                qq.bot, _click(next(iter(qq.module._pending)), selection, user="701")
            )
            if confirm is not None:
                await _wait_for_send(qq, 2)
                final_click = _click(next(iter(qq.module._pending)), confirm, user="701")
                await qq.module._handle_account_button(qq.bot, final_click)
            await task
        accounts = list(await session.scalars(select(SkUser).where(SkUser.owner_id == 701)))
        assert len(accounts) == remaining
        if selection == "1" and confirm == "confirm":
            assert [account.skland_user_id for account in accounts] == ["remote-2"]
        if confirm is not None:
            assert qq.calls[-1][0] is final_click
        waiter.assert_not_awaited()
