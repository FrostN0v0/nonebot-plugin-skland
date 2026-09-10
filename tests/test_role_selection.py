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
        (f"/skland arksign status {flag} 2", "arksign.status.role.role_index"),
        (f"/skland efsign status {flag} 2", "efsign.status.role.role_index"),
        (f"/skland gacha {flag} 2 -b 1 -l 3", "gacha.role.role_index"),
        (f"/skland efgacha {flag} 2", "efgacha.role.role_index"),
        (f"/skland efwar {flag} 2 -s 3 -w 2", "efwar.role.role_index"),
        (f"/skland import https://example.com/export {flag} 2", "import.role.role_index"),
        (f"/skland rogue {flag} 2 --topic 萨米", "rogue.role.role_index"),
        (f"/skland rginfo 1 -f {flag} 2", "rginfo.role.role_index"),
        (f"/skland box {flag} 2 -ra 6", "box.role.role_index"),
    ):
        result = skland_command.parse(command)
        assert result.matched, command
        assert result.query(path) == 2
        if result.subcommands:
            assert not result.find("role")
        assert not skland_command.parse(command.replace(f"{flag} 2", f"{flag} invalid")).matched


@pytest.mark.parametrize(
    "options",
    ["-r 2 -ra 6", "-ra 6 -r 2", "--role 2 --rarity 6"],
)
def test_roster_role_and_rarity_options_do_not_overlap(app, options):
    from nonebot_plugin_skland.matcher import skland_command

    result = skland_command.parse(f"/skland box {options}")
    assert result.matched
    assert result.query("box.role.role_index") == 2
    assert result.query("box.rarity.rarities") == "6"
    assert not result.find("role")


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
    ):
        result = skland_command.parse(command)
        assert result.matched, command
        assert result.find(path)
        assert not result.find("role")


@pytest.mark.parametrize(
    "command",
    [
        "/skland -r 0",
        "/skland efcard -r 0",
        "/skland gacha -r 0",
        "/skland efgacha -r 0",
        "/skland efwar -r 0",
        "/skland import https://example.com/export -r 0",
        "/skland box -r 0 -ra 6",
        "/skland rogue -r 0",
        "/skland rginfo 1 -r 0",
        "/skland arksign sign -r 0",
        "/skland efsign sign -r 0",
        "/skland arksign status -r 0",
        "/skland efsign status -r 0",
    ],
)
@pytest.mark.asyncio
async def test_role_commands_reject_invalid_index_without_data_access(app, mocker, make_user_session, command):
    from nonebot import get_adapter
    from nonebot_plugin_user import UserSession
    from nonebot.internal.params import DependencyCache
    from nonebot_plugin_alconna import Image, UniMessage
    from nonebot_plugin_alconna.model import CommandResult
    from nonebot_plugin_alconna.consts import ALCONNA_RESULT, ALCONNA_EXTENSION
    from nonebot.adapters.onebot.v11 import Bot, Adapter, Message, PrivateMessageEvent
    from nonebot_plugin_orm import get_session, get_scoped_session, async_scoped_session

    import nonebot_plugin_skland.commands.card as ark_card
    import nonebot_plugin_skland.commands.box as box_command
    from nonebot_plugin_skland.model import SkUser, Character
    import nonebot_plugin_skland.commands.gacha as gacha_command
    import nonebot_plugin_skland.commands.selection as selection
    import nonebot_plugin_skland.commands.endfield.card as ef_card
    from nonebot_plugin_skland.api import SklandAPI, SklandLoginAPI
    from nonebot_plugin_skland.matcher import skland, skland_command
    import nonebot_plugin_skland.commands.endfield.war_echoes as ef_war
    from nonebot_plugin_skland.db_handler import set_default_character

    async with get_session() as session:
        account = SkUser(owner_id=901, access_token="access", cred="cred", cred_token="token", skland_user_id="remote")
        session.add(account)
        await session.flush()
        for game in ("arknights", "endfield"):
            character = Character(
                account_id=account.id,
                uid=game,
                role_id=game,
                app_code=game,
                channel_master_id="1",
                server_name="Server",
                nickname=game,
                is_skland_default=False,
            )
            session.add(character)
            await session.flush()
            await set_default_character(901, game, character.id, session)
        user_session = await make_user_session(session, 901, private=True)
        messages = []

        async def send(message, **kwargs):
            assert not session.in_transaction()
            messages.append(message)

        mocker.patch.object(UniMessage, "send", new=send)
        mocker.patch.object(selection, "render_bound_roles_card", new=mocker.AsyncMock(return_value=b"image"))
        ark_api = mocker.patch.object(ark_card, "get_ark_card", new=mocker.AsyncMock())
        ef_api = mocker.patch.object(ef_card.SklandAPI, "endfield_card", new=mocker.AsyncMock())
        ef_war_api = mocker.patch.object(ef_war.SklandAPI, "endfield_war_echoes", new=mocker.AsyncMock())
        remote_calls = [
            mocker.patch.object(SklandAPI, name, new=mocker.AsyncMock())
            for name in ("get_rogue", "ark_sign", "endfield_sign")
        ]
        remote_calls.append(mocker.patch.object(SklandLoginAPI, "get_grant_code", new=mocker.AsyncMock()))
        remote_calls.append(mocker.patch.object(gacha_command, "import_heybox_gacha_data", new=mocker.AsyncMock()))
        mocker.patch.object(box_command, "_build_query", return_value=mocker.sentinel.query)
        mocker.patch.object(box_command.gacha_table_data, "operator_catalog", mocker.Mock(entries={"fixture": None}))
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
                        {
                            ALCONNA_RESULT: CommandResult(result=result),
                            ALCONNA_EXTENSION: skland.executor.select(bot, event),
                        },
                        stack=stack,
                        dependency_cache=dependency_cache,
                    )
            finally:
                scoped_session.registry.clear()

        assert len(messages) == 1
        assert "sk char" in messages[0].extract_plain_text()
        assert messages[0][Image][0].raw == b"image"
        for remote_call in remote_calls:
            remote_call.assert_not_awaited()
        ark_api.assert_not_awaited()
        ef_api.assert_not_awaited()
        ef_war_api.assert_not_awaited()
        assert not session.in_transaction()
