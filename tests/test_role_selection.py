from typing import get_args
from contextlib import AsyncExitStack

import pytest


@pytest.mark.parametrize("flag", ["--role", "-r"])
def test_role_selectors_preserve_target_and_game_scope(app, flag):
    from nonebot_plugin_skland.matcher import skland_command

    bare_target = skland_command.parse("/skland 2")
    assert bare_target.matched
    assert bare_target.query("target") == 2
    assert not bare_target.find("role")

    for command, path in (
        (f"/skland {flag} 2", "role.role_index"),
        (f"/skland efcard {flag} 2 -a -s", "efcard.role.role_index"),
        (f"/skland arksign sign {flag} 2", "arksign.sign.role.role_index"),
        (f"/skland efsign sign {flag} 2", "efsign.sign.role.role_index"),
    ):
        result = skland_command.parse(command)
        assert result.matched, command
        assert result.query(path) == 2
        if result.subcommands:
            assert not result.find("role")
        assert not skland_command.parse(command.replace(f"{flag} 2", f"{flag} invalid")).matched


@pytest.mark.parametrize("command", ["arksign", "efsign"])
def test_uid_sign_selector_aliases_are_rejected(app, command):
    from nonebot_plugin_skland.matcher import skland_command

    for flag in ("-u", "--uid", "uid"):
        assert not skland_command.parse(f"/skland {command} sign {flag} 12345678").matched
    assert skland_command.parse(f"/skland {command} sign --all").matched
    assert skland_command.parse(f"/skland {command} sign").matched


def test_update_flags_keep_their_existing_meaning(app):
    from nonebot_plugin_skland.matcher import skland_command

    for command, path in (
        ("/skland bind token -u", "bind.update"),
        ("/skland char -u", "char.update"),
        ("/skland sync -u", "sync.update"),
        ("/skland efgacha -u", "efgacha.update"),
    ):
        result = skland_command.parse(command)
        assert result.matched, command
        assert result.find(path)
        assert not result.find("role")


@pytest.mark.parametrize("command", ["/skland -r 0", "/skland efcard -r 0"])
@pytest.mark.asyncio
async def test_indexed_card_command_dispatches_once_without_default_fallback(app, mocker, make_user_session, command):
    from nonebot import get_adapter
    from nonebot_plugin_user import UserSession
    from nonebot_plugin_alconna import UniMessage
    from nonebot.internal.params import DependencyCache
    from nonebot_plugin_alconna.model import CommandResult
    from nonebot_plugin_alconna.consts import ALCONNA_RESULT
    from nonebot.adapters.onebot.v11 import Bot, Adapter, Message, PrivateMessageEvent
    from nonebot_plugin_orm import get_session, get_scoped_session, async_scoped_session

    from nonebot_plugin_skland.model import SkUser
    import nonebot_plugin_skland.commands.card as ark_card
    import nonebot_plugin_skland.commands.char as char_command
    import nonebot_plugin_skland.commands.endfield.card as ef_card
    from nonebot_plugin_skland.matcher import skland, skland_command

    async with get_session() as session:
        session.add(SkUser(owner_id=901, cred="cred", cred_token="token", skland_user_id="remote"))
        user_session = await make_user_session(session, 901, private=True)
        messages = []

        async def send(message, **kwargs):
            assert not session.in_transaction()
            messages.append(message.extract_plain_text())

        mocker.patch.object(UniMessage, "send", new=send)
        mocker.patch.object(char_command, "render_bound_roles_card", new=mocker.AsyncMock(return_value=b"image"))
        ark_api = mocker.patch.object(ark_card, "get_ark_card", new=mocker.AsyncMock())
        ef_api = mocker.patch.object(ef_card.SklandAPI, "endfield_card", new=mocker.AsyncMock())
        bot = Bot(get_adapter(Adapter), "12345")
        event = PrivateMessageEvent(
            time=0,
            self_id=12345,
            post_type="message",
            sub_type="friend",
            user_id=901,
            message_type="private",
            message_id=1,
            message=Message(command),
            original_message=Message(command),
            raw_message=command,
            font=0,
            sender={"user_id": 901},
        )
        result = skland_command.parse(command)
        assert result.matched
        matcher = skland()
        with matcher.ensure_context(bot, event):
            scoped_session = get_scoped_session()
            scoped_session.registry.set(session)
            try:
                dependency_cache = {}
                for annotation, value in ((async_scoped_session, scoped_session), (UserSession, user_session)):
                    cached_dependency = DependencyCache()
                    cached_dependency.set_result(value)
                    dependency_cache[get_args(annotation)[1].dependency] = cached_dependency
                async with AsyncExitStack() as stack:
                    await matcher.run(
                        bot,
                        event,
                        {ALCONNA_RESULT: CommandResult(result=result)},
                        stack=stack,
                        dependency_cache=dependency_cache,
                    )
            finally:
                scoped_session.registry.clear()

        assert len(messages) == 1
        assert "sk char" in messages[0]
        ark_api.assert_not_awaited()
        ef_api.assert_not_awaited()
        assert not session.in_transaction()
