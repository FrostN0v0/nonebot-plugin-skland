import os
import sys
import importlib
import subprocess
from typing import get_args
from types import SimpleNamespace
from unittest.mock import AsyncMock
from contextlib import AsyncExitStack

import pytest

pytest.importorskip("nonebot.adapters.qq")


@pytest.fixture
def maa(app, tmp_path, mocker):
    from nonebot_plugin_skland.config import config

    mocker.patch.object(config.maa, "data_dir", tmp_path / "maa")
    mocker.patch.object(config.maa, "public_url", "https://maa.example.com")
    module = importlib.import_module("nonebot_plugin_skland.integrations.maa.runtime")
    from nonebot_plugin_skland.integrations.maa.core import Store
    from nonebot_plugin_skland.integrations.maa.commands import Commands

    store = Store(tmp_path / "maa")
    mocker.patch.object(module, "store", store)
    mocker.patch.object(module, "commands", Commands(store, "https://maa.example.com"))
    from nonebot_plugin_skland.integrations.maa.binding_qq import BindingFlow

    binding = BindingFlow(tmp_path / "binding/pairing.sqlite3", None, store, "https://maa.example.com", module.log)
    binding.server = object()  # This test exercises QQ routing, not the Unix listener.
    mocker.patch.object(module, "binding_flow", binding)
    return module


def qq_bot():
    import nonebot
    from nonebot.adapters.qq import Bot, Adapter

    driver = nonebot.get_driver()
    if Adapter.get_name() not in driver._adapters:
        driver.register_adapter(Adapter)
    from nonebot.adapters.qq.config import BotInfo

    return Bot(nonebot.get_adapter(Adapter), "test-bot", BotInfo(id="test-bot", secret="test-secret"))


def private_event(text, user="alice", message_id="message"):
    from nonebot.adapters.qq import Message, C2CMessageCreateEvent

    return C2CMessageCreateEvent.model_construct(
        id=message_id, author=SimpleNamespace(user_openid=user), message=Message(text)
    )


def test_alconna_commands_and_shortcuts(maa):
    from nonebot_plugin_skland.integrations.maa.matcher import command

    for text, operation, argument in (
        ("/maa", None, None),
        ("/MAA", None, None),
        ("/maa 任务", "任务", None),
        ("/maa 开始 基建", "开始", "基建"),
        ("/MAA绑定", "绑定", None),
        ("/maa状态", "状态", None),
    ):
        result = command.parse(text)
        assert result.matched, (text, result.error_info)
        assert result.main_args.get("operation") == operation
        assert result.main_args.get("argument") == argument
    assert not command.parse("/maa菜单").matched


@pytest.mark.asyncio
async def test_both_scenes_create_web_request_without_disclosing_key(maa):
    from nonebot.adapters.qq import Message, GroupMessageCreateEvent

    from nonebot_plugin_skland.integrations.maa.core import digest
    from nonebot_plugin_skland.integrations.maa.matcher import command

    bot = qq_bot()
    matcher = SimpleNamespace(send=AsyncMock(), finish=AsyncMock())
    session = SimpleNamespace(user_id=101)
    await maa.handle(matcher, bot, private_event("/maa绑定"), command.parse("/maa绑定"), session)
    reply = str(matcher.send.call_args.args[0])
    assert "https://maa.example.com/maa/bind?request=" in reply
    assert "用户标识符：maa_" not in reply
    owner = digest(f"{bot.self_id}:user:101")
    assert maa.store.view(owner)[0] is None

    group = GroupMessageCreateEvent.model_construct(
        id="group-bind",
        group_openid="test-group",
        content="/maa绑定",
        attachments=[],
        author=SimpleNamespace(member_openid="bob"),
        message=Message("/maa绑定"),
    )
    await maa.handle(matcher, bot, group, command.parse("/maa绑定"), session)
    reply = str(matcher.send.call_args.args[0])
    assert "https://maa.example.com/maa/bind?request=" in reply
    assert "用户标识符" not in reply


@pytest.mark.asyncio
async def test_private_button_replies_with_submenu_and_rejects_other_users(maa, mocker):
    from nonebot.adapters.qq import InteractionCreateEvent

    from nonebot_plugin_skland.integrations.maa.matcher import command

    bot = qq_bot()
    put = mocker.patch.object(bot, "put_interaction", new=AsyncMock())
    send = mocker.patch.object(bot, "send_to_c2c", new=AsyncMock())
    matcher = SimpleNamespace(send=AsyncMock(), finish=AsyncMock())
    await maa.handle(matcher, bot, private_event("/maa"), command.parse("/maa"), SimpleNamespace(user_id=101))
    keyboard = matcher.send.call_args.args[0][1].data["keyboard"].content
    assert all(len(row.buttons) == 1 for row in keyboard.rows)
    button = keyboard.rows[1].buttons[0]
    assert button.action.type == 1
    assert button.action.permission.type == 2
    click = InteractionCreateEvent.model_construct(
        id="interaction",
        event_id="event",
        type=11,
        chat_type=2,
        user_openid="bob",
        data=SimpleNamespace(resolved=SimpleNamespace(button_data=button.action.data)),
    )
    await maa.handle_click(bot, click)
    put.assert_awaited_with(interaction_id="interaction", code=1)
    send.assert_not_awaited()
    click.user_openid = "alice"
    await maa.handle_click(bot, click)
    put.assert_awaited_with(interaction_id="interaction", code=0)
    assert "状态与截图" in str(send.call_args.kwargs["message"])
    assert send.call_args.kwargs["event_id"] == "event"
    await maa.handle_click(bot, click)
    assert send.await_count == 1


@pytest.mark.asyncio
async def test_group_callback_uses_bound_user_and_persists_notification_origin(maa, mocker):
    from nonebot.adapters.qq import Message, InteractionCreateEvent, GroupMessageCreateEvent

    from nonebot_plugin_skland.integrations.maa.core import digest
    from nonebot_plugin_skland.integrations.maa.matcher import command

    bot = qq_bot()
    owner = digest(f"{bot.self_id}:user:202")
    key = maa.store.issue(owner)
    maa.store.poll(key, "test-device")
    mocker.patch.object(bot, "put_interaction", new=AsyncMock())
    send = mocker.patch.object(bot, "send_to_group", new=AsyncMock())
    group = GroupMessageCreateEvent.model_construct(
        id="group-menu",
        group_openid="test-group",
        content="/maa 任务",
        attachments=[],
        author=SimpleNamespace(member_openid="group-alice"),
        message=Message("/maa 任务"),
    )
    matcher = SimpleNamespace(send=AsyncMock(), finish=AsyncMock())
    await maa.handle(matcher, bot, group, command.parse("/maa 任务"), SimpleNamespace(user_id=202))
    keyboard = matcher.send.call_args.args[0][1].data["keyboard"].content
    click = InteractionCreateEvent.model_construct(
        id="group-click",
        event_id="group-event",
        type=11,
        chat_type=1,
        group_openid="test-group",
        group_member_openid="group-alice",
        data=SimpleNamespace(resolved=SimpleNamespace(button_data=keyboard.rows[1].buttons[0].action.data)),
    )
    await maa.handle_click(bot, click)
    assert "已提交" in str(send.call_args.kwargs["message"])
    task = maa.store.poll(key, "test-device")["tasks"][0]
    assert task["type"] == "LinkStart-Combat"
    with maa.store.db() as db:
        origin = db.execute("SELECT * FROM task_origin WHERE task_id=?", (task["id"],)).fetchone()
    assert (origin["bot_id"], origin["scene"], origin["target"]) == (bot.self_id, "group", "test-group")


def test_menu_scope_expiry_and_cert_not_exposed_in_help(maa):
    from nonebot_plugin_skland.integrations.maa.commands import HELP
    from nonebot_plugin_skland.integrations.maa.menu import PAGES, Menus

    clock = [0]
    menus = Menus(clock=lambda: clock[0])
    nonce = menus.create("bot", "alice", "group", False, "owner", [("状态", "/MAA状态")])
    data = f"maamenu:{nonce}:0"
    assert menus.claim(data, "bot", "alice", "other-group") is None
    assert menus.claim(data, "bot", "bob", "group") is None
    clock[0] = 601
    assert menus.claim(data, "bot", "alice", "group") is None
    assert "证书" not in HELP
    assert "证书" not in str(PAGES)


def test_disabled_module_does_not_register_help(app):
    from nonebot_plugin_skland.config import MaaConfig
    from nonebot_plugin_skland.extras import HELP_ENTRIES

    assert not MaaConfig().enabled
    assert all(entry.func != "MAA 远控" for entry in HELP_ENTRIES)


@pytest.mark.asyncio
async def test_private_control_and_result_origin(maa):
    from nonebot_plugin_skland.integrations.maa.core import digest
    from nonebot_plugin_skland.integrations.maa.matcher import command

    bot = qq_bot()
    owner = digest(f"{bot.self_id}:user:101")
    key = maa.store.issue(owner)
    maa.store.poll(key, "device")
    matcher = SimpleNamespace(send=AsyncMock(), finish=AsyncMock())
    await maa.handle(
        matcher, bot, private_event("/maa 开始 基建"), command.parse("/maa 开始 基建"), SimpleNamespace(user_id=101)
    )
    assert "已提交" in str(matcher.send.call_args.args[0])
    task = maa.store.poll(key, "device")["tasks"][0]
    with maa.store.db() as db:
        row = db.execute("SELECT * FROM task_origin WHERE task_id=?", (task["id"],)).fetchone()
    assert (row["scene"], row["target"]) == ("private", "alice")


@pytest.mark.asyncio
async def test_admin_menu_private_and_superuser_only_and_hidden(maa, mocker):
    from nonebot_plugin_skland.extras import HELP_ENTRIES
    from nonebot_plugin_skland.integrations.maa import admin_menu as admin

    matcher = SimpleNamespace(send=AsyncMock())
    bot = qq_bot()
    event = private_event("/超管菜单")
    mocker.patch.object(admin, "SUPERUSER", new=AsyncMock(return_value=False))
    await admin.show_admin_menu(bot, event, matcher)
    matcher.send.assert_not_awaited()
    mocker.patch.object(admin, "SUPERUSER", new=AsyncMock(return_value=True))
    await admin.show_admin_menu(bot, object(), matcher)
    matcher.send.assert_not_awaited()
    await admin.show_admin_menu(bot, event, matcher)
    assert "/MAA证书" in str(matcher.send.call_args.args[0])
    assert "超管菜单" not in str(HELP_ENTRIES)


@pytest.mark.asyncio
@pytest.mark.parametrize(("text", "expected"), [("/MAA绑定", "/maa/bind?request="), ("/maa状态", "尚未绑定")])
async def test_registered_matcher_resolves_framework_dependencies(maa, mocker, make_user_session, text, expected):
    from nonebot_plugin_orm import get_session
    from nonebot_plugin_user import UserSession
    from nonebot.internal.params import DependencyCache

    from nonebot_plugin_skland.integrations.maa.matcher import control

    bot = qq_bot()
    event = private_event(text, message_id="matcher-shortcut-" + text)
    send = mocker.patch.object(control, "send", new=AsyncMock())
    cached = DependencyCache()
    async with get_session() as session:
        user_session = await make_user_session(session, 303, private=True)
    cached.set_result(user_session)
    matcher = control()
    state = {}
    dependencies = {get_args(UserSession)[1].dependency: cached}
    with matcher.ensure_context(bot, event):
        async with AsyncExitStack() as stack:
            assert await control.check_rule(bot, event, state, stack, dependencies)
            await matcher.run(
                bot,
                event,
                state,
                stack=stack,
                dependency_cache=dependencies,
            )
    assert send.call_args is not None, repr(control.handlers)
    assert expected in str(send.call_args.args[0])


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["/maa", "/MAA"])
@pytest.mark.parametrize("main_args", [{}, {"operation": None, "argument": None}])
async def test_bare_command_opens_home_menu(maa, text, main_args):
    matcher = SimpleNamespace(send=AsyncMock(), finish=AsyncMock())
    await maa.handle(
        matcher, qq_bot(), private_event(text), SimpleNamespace(main_args=main_args), SimpleNamespace(user_id=101)
    )
    message = matcher.send.call_args.args[0]
    assert "MAA 远程控制" in str(message)
    keyboard = message[1].data["keyboard"].content
    assert keyboard.rows[0].buttons[0].render_data.label == "绑定设备"


@pytest.mark.parametrize("enabled", [False, True])
def test_plugin_loads_with_module_enabled_or_disabled(tmp_path, enabled):
    script = """
import os, sys, nonebot
from pathlib import Path
directory = Path(sys.argv[1])
enabled = sys.argv[2] == 'True'
nonebot.init(
    _env_file=os.devnull, driver='~fastapi+~httpx',
    localstore_data_dir=directory / 'data', localstore_cache_dir=directory / 'cache',
    localstore_config_dir=directory / 'config',
    skland={'maa': {'enabled': enabled, 'public_url': 'https://maa.example.com', 'data_dir': str(directory / 'maa')}},
)
assert nonebot.load_plugin('nonebot_plugin_skland')
assert ('nonebot_plugin_skland.integrations.maa.runtime' in sys.modules) == enabled
assert (directory / 'maa/maa.sqlite3').exists() == enabled
from nonebot_plugin_skland.extras import HELP_ENTRIES
assert any(e.func == 'MAA 远控' for e in HELP_ENTRIES) == enabled
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), str(enabled)],
        env={**os.environ, "SKLAND": "{}"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
