import json
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, inspect


async def _seed_sign_roles(session, owner_id: int):
    from nonebot_plugin_skland.model import SkUser, Character

    accounts = []
    for suffix in ("a", "b"):
        account = SkUser(
            owner_id=owner_id,
            access_token=f"access-{suffix}",
            cred=f"cred-{suffix}",
            cred_token=f"token-{suffix}",
            skland_user_id=f"remote-{suffix}",
        )
        session.add(account)
        await session.flush()
        accounts.append(account)
        session.add_all(
            [
                Character(
                    account_id=account.id,
                    uid="ark-shared",
                    role_id=f"ark-{suffix}",
                    app_code="arknights",
                    channel_master_id=suffix,
                    server_name=f"Ark {suffix.upper()}",
                    nickname="Same Name",
                    level=None,
                    is_skland_default=False,
                ),
                Character(
                    account_id=account.id,
                    uid="ef-shared",
                    role_id=f"ef-{suffix}",
                    app_code="endfield",
                    channel_master_id=suffix,
                    server_name=f"EF {suffix.upper()}",
                    nickname="Same Name",
                    level=10,
                    is_skland_default=False,
                ),
            ]
        )
    await session.commit()
    return accounts


def test_sign_formatters_preserve_duplicate_titles_and_errors(app):
    from nonebot_plugin_skland.utils import format_sign_result, format_endfield_sign_result

    ark_data = [
        {
            "owner_id": 1,
            "character_id": 1,
            "nickname": "Same",
            "role_id": "role",
            "server_id": "1",
            "server_name": "Server",
            "result": {"awards": [{"resource": {"name": "LMD"}, "count": 1}]},
        },
        {
            "owner_id": 1,
            "character_id": 2,
            "nickname": "Same",
            "role_id": "role",
            "server_id": "1",
            "server_name": "Server",
            "result": "request failed",
        },
    ]
    ark = format_sign_result(ark_data, "2026-09-04 00:15", False)
    assert len(ark.results) == 2
    assert ark.results[0][0] == ark.results[1][0]
    assert ark.success_count == 1
    assert ark.failed_count == 1

    ef_data = [
        {
            **ark_data[0],
            "result": {
                "awardIds": [{"id": "item"}],
                "resourceInfoMap": {"item": {"name": "Currency", "count": 2}},
            },
        },
        {**ark_data[1], "result": "请勿重复签到"},
    ]
    endfield = format_endfield_sign_result(ef_data, "2026-09-04 00:20", True)
    assert len(endfield.results) == 2
    assert endfield.success_count == 2
    assert endfield.failed_count == 0


@pytest.mark.asyncio
async def test_personal_sign_all_uses_each_roles_account_credentials(app, mocker):
    from nonebot_plugin_orm import get_session

    import nonebot_plugin_skland.commands.arksign as arksign
    import nonebot_plugin_skland.commands.endfield.sign as efsign
    from nonebot_plugin_skland.schemas import ArkSignResponse, EndfieldSignResponse

    async with get_session() as session:
        await _seed_sign_roles(session, 60)
        user_session = SimpleNamespace(user_id=60, platform="Console")
        ark_result = SimpleNamespace(find=lambda path: path == "arksign.sign.all")
        ef_result = SimpleNamespace(find=lambda path: path == "efsign.sign.all")
        ark_calls = []
        ef_calls = []

        async def ark_sign(cred, uid, *, channel_master_id):
            ark_calls.append((cred.cred, cred.token, uid, channel_master_id))
            return ArkSignResponse(awards=[])

        async def ef_sign(cred, role_id, *, server_id):
            ef_calls.append((cred.cred, cred.token, role_id, server_id))
            return EndfieldSignResponse(ts="", awardIds=[], resourceInfoMap={}, tomorrowAwardIds=[])

        mocker.patch.object(arksign.SklandAPI, "ark_sign", new=ark_sign)
        mocker.patch.object(efsign.SklandAPI, "endfield_sign", new=ef_sign)
        mocker.patch.object(arksign, "send_reaction")
        mocker.patch.object(efsign, "send_reaction")
        mocker.patch.object(arksign.UniMessage, "send", new=mocker.AsyncMock())
        mocker.patch.object(efsign.UniMessage, "send", new=mocker.AsyncMock())

        await arksign.arksign_sign_handler(user_session, session, None, ark_result)
        await efsign.ef_sign_handler(user_session, session, None, ef_result)

        assert ark_calls == [
            ("cred-a", "token-a", "ark-shared", "a"),
            ("cred-b", "token-b", "ark-shared", "b"),
        ]
        assert ef_calls == [
            ("cred-a", "token-a", "ef-a", "a"),
            ("cred-b", "token-b", "ef-b", "b"),
        ]


@pytest.mark.asyncio
async def test_scheduled_sign_cache_uses_ordered_identity_entries(app, mocker, tmp_path):
    from nonebot_plugin_orm import get_session

    import nonebot_plugin_skland.tasks as tasks
    from nonebot_plugin_skland.schemas import ArkSignResponse, EndfieldSignResponse

    async with get_session() as session:
        await _seed_sign_roles(session, 70)

    mocker.patch.object(tasks, "CACHE_DIR", tmp_path)
    mocker.patch.object(tasks, "_ark_sign_in", new=mocker.AsyncMock(return_value=ArkSignResponse(awards=[])))
    mocker.patch.object(
        tasks,
        "_endfield_sign_in",
        new=mocker.AsyncMock(
            return_value=EndfieldSignResponse(ts="", awardIds=[], resourceInfoMap={}, tomorrowAwardIds=[])
        ),
    )

    await tasks.run_daily_arksign()
    await tasks.run_daily_efsign()

    ark_cache = json.loads((tmp_path / "sign_result.json").read_text(encoding="utf-8"))
    ef_cache = json.loads((tmp_path / "endfield_sign_result.json").read_text(encoding="utf-8"))
    for cache, prefix in ((ark_cache, "ark-"), (ef_cache, "ef-")):
        assert isinstance(cache["data"], list)
        assert len(cache["data"]) == 2
        assert [entry["nickname"] for entry in cache["data"]] == ["Same Name", "Same Name"]
        assert [entry["role_id"] for entry in cache["data"]] == [f"{prefix}a", f"{prefix}b"]
        assert all(entry["owner_id"] == 70 for entry in cache["data"])


@pytest.mark.parametrize("game", ["arknights", "endfield"])
@pytest.mark.parametrize("selection", ["invalid_index", "empty_all"])
@pytest.mark.asyncio
async def test_sign_selection_feedback_survives_expired_user_session(app, mocker, make_user_session, game, selection):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.model import Character
    import nonebot_plugin_skland.commands.arksign as arksign
    import nonebot_plugin_skland.commands.char as char_command
    import nonebot_plugin_skland.commands.endfield.sign as efsign

    command, handler, all_path, api_name = (
        (arksign, arksign.arksign_sign_handler, "arksign.sign.all", "ark_sign")
        if game == "arknights"
        else (efsign, efsign.ef_sign_handler, "efsign.sign.all", "endfield_sign")
    )
    async with get_session() as session:
        await _seed_sign_roles(session, 90)
        if selection == "empty_all":
            await session.execute(delete(Character).where(Character.app_code == game))
        user_session = await make_user_session(session, 90)
        rendered_cards = []
        messages = []

        async def render(card):
            assert session.in_transaction() is False
            assert inspect(user_session.user).expired
            rendered_cards.append(card)
            return b"card"

        async def send(message, **_kwargs):
            assert session.in_transaction() is False
            assert inspect(user_session.user).expired
            messages.append(message.extract_plain_text().strip())

        mocker.patch.object(char_command, "render_bound_roles_card", new=render)
        mocker.patch.object(command.UniMessage, "send", new=send)
        sign = mocker.patch.object(command.SklandAPI, api_name, new=mocker.AsyncMock())

        role_index = None if selection == "empty_all" else 999
        result = SimpleNamespace(find=lambda path: path == all_path if selection == "empty_all" else False)
        await handler(user_session, session, role_index, result)

        assert session.in_transaction() is False
        assert len(rendered_cards) == 1
        assert len(messages) == 1
        assert messages[0]
        sign.assert_not_awaited()


@pytest.mark.parametrize("game", ["arknights", "endfield"])
@pytest.mark.parametrize(
    ("default_index", "role_index", "expected_suffix"),
    [(1, 2, "b"), (None, 2, "b"), (1, None, "a")],
)
@pytest.mark.asyncio
async def test_sign_selection_uses_owning_account_without_changing_defaults(
    app, mocker, make_user_session, game, default_index, role_index, expected_suffix
):
    from nonebot_plugin_orm import get_session

    import nonebot_plugin_skland.commands.arksign as arksign
    import nonebot_plugin_skland.commands.endfield.sign as efsign
    from nonebot_plugin_skland.schemas import ArkSignResponse, EndfieldSignResponse
    from nonebot_plugin_skland.db_handler import get_user_characters, get_default_character, set_default_character

    command, handler = (
        (arksign, arksign.arksign_sign_handler) if game == "arknights" else (efsign, efsign.ef_sign_handler)
    )
    async with get_session() as session:
        await _seed_sign_roles(session, 100)
        expected_defaults = {}
        for app_code in ("arknights", "endfield"):
            characters = await get_user_characters(100, app_code, session)
            expected_defaults[app_code] = characters[default_index - 1].id if default_index is not None else None
            if default_index is not None:
                await set_default_character(100, app_code, expected_defaults[app_code], session)
        await session.commit()
        user_session = await make_user_session(session, 100)
        calls = []

        if game == "arknights":

            async def ark_sign(cred, uid, *, channel_master_id):
                calls.append((cred.cred, cred.token, uid, channel_master_id))
                return ArkSignResponse(awards=[])

            mocker.patch.object(command.SklandAPI, "ark_sign", new=ark_sign)
        else:

            async def ef_sign(cred, role_id, *, server_id):
                calls.append((cred.cred, cred.token, role_id, server_id))
                return EndfieldSignResponse(ts="", awardIds=[], resourceInfoMap={}, tomorrowAwardIds=[])

            mocker.patch.object(command.SklandAPI, "endfield_sign", new=ef_sign)

        mocker.patch.object(command, "send_reaction")
        mocker.patch.object(command.UniMessage, "send", new=mocker.AsyncMock())
        await handler(user_session, session, role_index, SimpleNamespace(find=lambda _path: False))

        expected_role = "ark-shared" if game == "arknights" else f"ef-{expected_suffix}"
        assert calls == [(f"cred-{expected_suffix}", f"token-{expected_suffix}", expected_role, expected_suffix)]
        for app_code, character_id in expected_defaults.items():
            current_default = await get_default_character(100, app_code, session)
            assert (current_default.id if current_default else None) == character_id


@pytest.mark.parametrize("game", ["arknights", "endfield"])
@pytest.mark.parametrize("operation", ["sign", "status"])
@pytest.mark.asyncio
async def test_role_index_and_all_are_rejected_without_side_effects(app, mocker, make_user_session, game, operation):
    from nonebot_plugin_orm import get_session

    import nonebot_plugin_skland.commands.arksign as arksign
    import nonebot_plugin_skland.commands.endfield.sign as efsign

    command, handler, all_path, api_name = (
        (arksign, arksign.arksign_sign_handler, "arksign.sign.all", "ark_sign")
        if game == "arknights"
        else (efsign, efsign.ef_sign_handler, "efsign.sign.all", "endfield_sign")
    )
    async with get_session() as session:
        await _seed_sign_roles(session, 130)
        user_session = await make_user_session(session, 130)
        messages = []

        async def send(message, **_kwargs):
            assert session.in_transaction() is False
            messages.append(message.extract_plain_text())

        mocker.patch.object(command.UniMessage, "send", new=send)
        reaction = mocker.patch.object(command, "send_reaction")
        sign = mocker.patch.object(command.SklandAPI, api_name, new=mocker.AsyncMock())

        if operation == "sign":
            await handler(user_session, session, 2, SimpleNamespace(find=lambda path: path == all_path))
        else:
            status_handler = arksign.arksign_status_handler if game == "arknights" else efsign.ef_sign_status_handler
            await status_handler(user_session, session, mocker.Mock(), True, is_superuser=True, role_index=2)

        assert session.in_transaction() is False
        assert len(messages) == 1
        assert "--role" in messages[0]
        assert "--all" in messages[0]
        reaction.assert_not_called()
        sign.assert_not_awaited()


@pytest.mark.parametrize("game", ["arknights", "endfield"])
@pytest.mark.parametrize("scope", ["selected", "personal", "global", "missing_selected"])
@pytest.mark.asyncio
async def test_sign_status_filters_role_and_owner_without_changing_defaults(
    app, mocker, make_user_session, tmp_path, game, scope
):
    from nonebot_plugin_orm import get_session

    import nonebot_plugin_skland.commands.arksign as arksign
    import nonebot_plugin_skland.commands.endfield.sign as efsign
    from nonebot_plugin_skland.db_handler import get_user_characters, get_default_character, set_default_character

    command, handler, cache_name = (
        (arksign, arksign.arksign_status_handler, "sign_result.json")
        if game == "arknights"
        else (efsign, efsign.ef_sign_status_handler, "endfield_sign_result.json")
    )
    async with get_session() as session:
        await _seed_sign_roles(session, 150)
        roles = await get_user_characters(150, game, session)
        default_id = roles[0].id
        await set_default_character(150, game, default_id, session)
        entries = [
            {
                "owner_id": 150,
                "character_id": role.id,
                "nickname": role.nickname,
                "role_id": role.role_id,
                "server_id": role.channel_master_id,
                "server_name": role.server_name,
                "result": f"cached-{index}",
            }
            for index, role in enumerate(roles)
        ]
        entries.append({**entries[1], "owner_id": 999, "result": "other-owner"})
        if scope == "missing_selected":
            entries.pop(1)
        (tmp_path / cache_name).write_text(json.dumps({"data": entries}), encoding="utf-8")
        mocker.patch.object(command, "CACHE_DIR", tmp_path)
        mocker.patch.object(command, "send_reaction")
        user_session = await make_user_session(session, 150)
        user_session.session.scope = "Console"
        if scope == "global":
            await session.commit()
            assert inspect(user_session.user).expired
        messages = []

        async def send(message, **_kwargs):
            assert not session.in_transaction()
            messages.append(message.extract_plain_text())

        mocker.patch.object(command.UniMessage, "send", new=send)
        await handler(
            user_session,
            session,
            mocker.Mock(),
            scope == "global",
            is_superuser=True,
            role_index=2 if scope in ("selected", "missing_selected") else None,
        )

        assert len(messages) == 1
        assert ("cached-0" in messages[0]) == (scope in ("personal", "global"))
        assert ("cached-1" in messages[0]) == (scope in ("selected", "personal", "global"))
        assert ("other-owner" in messages[0]) == (scope == "global")
        assert (await get_default_character(150, game, session)).id == default_id
