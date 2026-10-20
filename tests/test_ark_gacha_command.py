from types import SimpleNamespace

import pytest


def _pull(index=0):
    from nonebot_plugin_skland.schemas import GachaInfo

    return GachaInfo(
        poolId=f"pool-{index}",
        poolName=f"卡池{index}",
        charId="char_test",
        charName="测试干员",
        rarity=5,
        isNew=True,
        gachaTs=str((1700000000 + index) * 1000),
        pos=0,
    )


@pytest.fixture
async def ark_gacha_case(app, mocker, make_user_session, tiny_png):
    from nonebot_plugin_alconna import Match
    from nonebot_plugin_orm import get_session

    import nonebot_plugin_skland.commands.gacha as command
    import nonebot_plugin_skland.services.gacha as service
    from nonebot_plugin_skland.schemas import GachaCate, GachaResponse
    from nonebot_plugin_skland.schemas.arknights.game_data import CharTable
    from nonebot_plugin_skland.model import SkUser, Character, CharacterDefault

    async with get_session() as session:
        owner_id = 93001
        account = SkUser(
            owner_id=owner_id,
            access_token="test-access",
            cred="test-cred",
            cred_token="test-token",
            skland_user_id="test-remote-user",
        )
        session.add(account)
        await session.flush()
        character = Character(
            account_id=account.id,
            uid="test-role",
            role_id="test-role",
            app_code="arknights",
            channel_master_id="1",
            server_name="Official",
            nickname="博士",
            level=None,
            is_skland_default=True,
        )
        session.add(character)
        await session.flush()
        account_id, character_id = account.id, character.id
        session.add(CharacterDefault(owner_id=owner_id, app_code="arknights", character_id=character_id))
        user_session = await make_user_session(session, owner_id)
        session.sync_session.expire_on_commit = True
        pulls, messages = [], []

        async def fetch(*args, **kwargs):
            return GachaResponse(list=pulls, hasMore=False)

        async def profile(user, character):
            user.cred = "refreshed-cred"
            user.cred_token = "refreshed-token"
            return SimpleNamespace(status=SimpleNamespace(level=120))

        async def send(message, **kwargs):
            messages.append(message)

        mocker.patch.object(service.gacha_table_data, "gacha_table", [])
        mocker.patch.object(service.gacha_table_data, "gacha_details", [])
        mocker.patch.object(
            service.gacha_table_data,
            "character_table",
            [
                CharTable(char_id="char_test", name="测试干员"),
                CharTable(char_id="char_yato", name="麒麟R夜刀"),
            ],
        )
        mocker.patch.object(command.config, "gacha_render_max", 3)
        mocker.patch.object(command.SklandLoginAPI, "get_grant_code", new=mocker.AsyncMock(return_value="test-grant"))
        mocker.patch.object(
            command.SklandLoginAPI, "get_role_token_by_uid", new=mocker.AsyncMock(return_value="test-role-token")
        )
        mocker.patch.object(command.SklandLoginAPI, "get_ak_cookie", new=mocker.AsyncMock(return_value="test-cookie"))
        mocker.patch.object(
            command.SklandAPI,
            "get_gacha_categories",
            new=mocker.AsyncMock(return_value=[GachaCate(id="normal", name="标准寻访")]),
        )
        mocker.patch.object(service.SklandAPI, "get_gacha_history", new=mocker.AsyncMock(side_effect=fetch))
        profile_mock = mocker.patch.object(command, "get_ark_card", new=mocker.AsyncMock(side_effect=profile))
        render_mock = mocker.patch.object(command, "render_gacha_history", new=mocker.AsyncMock(return_value=tiny_png))
        mocker.patch.object(command.UniMessage, "send", new=send)
        reaction_mock = mocker.patch.object(command, "send_reaction")
        error_mock = mocker.patch.object(command, "send_request_error", new=mocker.AsyncMock())

        async def run(*, begin=None, limit=None):
            await command.gacha_handler(
                user_session,
                session,
                Match(begin, available=begin is not None),
                Match(limit, available=limit is not None),
                Match(None, available=False),
                SimpleNamespace(self_id="bot"),
            )

        yield SimpleNamespace(
            command=command,
            service=service,
            session=session,
            user_session=user_session,
            account_id=account_id,
            character_id=character_id,
            pulls=pulls,
            messages=messages,
            profile=profile_mock,
            render=render_mock,
            reaction=reaction_mock,
            error=error_mock,
            run=run,
        )


@pytest.mark.parametrize("platform", ["QQClient", "Discord"])
@pytest.mark.parametrize(("begin", "limit"), [(2, 10), (2, None), (-9, -1), (-4, None), (2, 4), (9, 4)])
@pytest.mark.asyncio
async def test_pool_slice_renders_each_selected_pool_once(ark_gacha_case, mocker, tiny_png, platform, begin, limit):
    case = ark_gacha_case
    case.pulls.extend(_pull(index) for index in range(11))
    mocker.patch.object(type(case.user_session), "platform", new_callable=mocker.PropertyMock, return_value=platform)
    node_mock = mocker.patch.object(case.command, "CustomNode", wraps=case.command.CustomNode)
    rendered_bounds, rendered_pools = [], []

    async def render(record, status, *, nickname, channel_master_id, begin, limit):
        assert nickname == "博士"
        assert channel_master_id == "1"
        rendered_bounds.append((begin, limit))
        rendered_pools.extend(pool.gachaPoolId for pool in record.pools[begin:limit])
        return tiny_png

    case.render.side_effect = render

    await case.run(begin=begin, limit=limit)

    start, stop, _ = slice(begin, limit).indices(11)
    expected_bounds = [(page_start, min(page_start + 3, stop)) for page_start in range(start, stop, 3)]
    if max(0, stop - start) <= 3:
        expected_bounds = [(start, stop)]
    assert rendered_bounds == expected_bounds
    assert rendered_pools == [f"pool-{index}" for index in range(start, stop)]
    assert all(page_stop <= stop for _, page_stop in rendered_bounds)
    if platform == "QQClient" and stop - start > 3:
        assert [call.args[1] for call in node_mock.call_args_list] == [
            f"博士 | {page_start}-{page_stop}" for page_start, page_stop in expected_bounds
        ]
    assert case.reaction.call_args.args[1] == "done"


@pytest.mark.parametrize("failure", ["profile", "profile_unexpected", "render", "send"])
@pytest.mark.asyncio
async def test_fetched_records_and_refreshed_credentials_survive_presentation_failure(ark_gacha_case, mocker, failure):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.model import SkUser
    from nonebot_plugin_skland.exception import RequestException
    from nonebot_plugin_skland.db_handler import get_character_gacha_records

    case = ark_gacha_case
    case.pulls.append(_pull())
    if failure.startswith("profile"):
        unexpected = failure == "profile_unexpected"

        async def profile(user, character):
            user.cred = "refreshed-cred"
            user.cred_token = "refreshed-token"
            if unexpected:
                raise ValueError("profile response changed")
            raise RequestException("profile unavailable")

        case.profile.side_effect = profile
        if unexpected:
            with pytest.raises(ValueError, match="profile response changed"):
                await case.run()
            case.error.assert_not_awaited()
        else:
            await case.run()
            case.error.assert_awaited_once()
        case.render.assert_not_awaited()
    else:
        if failure == "render":
            case.render.side_effect = RuntimeError("presentation unavailable")
        else:

            async def send(message, **kwargs):
                raise RuntimeError("presentation unavailable")

            mocker.patch.object(case.command.UniMessage, "send", new=send)
        with pytest.raises(RuntimeError, match="presentation unavailable"):
            await case.run()

    await case.session.rollback()
    async with get_session() as fresh:
        records = await get_character_gacha_records(case.character_id, fresh)
        assert [(record.pool_id, record.char_id, record.gacha_ts, record.pos) for record in records] == [
            ("pool-0", "char_test", 1700000000, 0)
        ]
        account = await fresh.get(SkUser, case.account_id)
        assert (account.cred, account.cred_token) == ("refreshed-cred", "refreshed-token")
    assert "done" not in [call.args[1] for call in case.reaction.call_args_list]


@pytest.mark.asyncio
async def test_import_rejects_all_unknown_names_without_saving_partial_records(ark_gacha_case, mocker):
    from nonebot_plugin_alconna import Match
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.db_handler import get_character_gacha_records
    from nonebot_plugin_skland.exception import UnresolvedGachaCharacterError

    case = ark_gacha_case
    data = {
        "1700000000": {"p": "未收录卡池", "c": [["测试干员", 5, True], ["UnknownB", 5, True]]},
        "1700000010": {"p": "未收录卡池", "c": [["UnknownA", 4, True], ["UnknownB", 5, False]]},
    }
    assert case.service.get_char_id_by_char_name("UnknownA") is None
    with pytest.raises(UnresolvedGachaCharacterError) as error:
        case.service.heybox_data_to_record(data, case.character_id)
    assert error.value.names == ["UnknownA", "UnknownB"]
    mocker.patch.object(
        case.command,
        "import_heybox_gacha_data",
        new=mocker.AsyncMock(return_value={"info": {"uid": "test-role"}, "data": data}),
    )

    await case.command.import_handler(
        Match("https://example.com/export", available=True), case.user_session, case.session
    )

    await case.session.rollback()
    async with get_session() as fresh:
        assert await get_character_gacha_records(case.character_id, fresh) == []
    visible = "\n".join(message.extract_plain_text() for message in case.messages)
    assert visible.count("UnknownA") == visible.count("UnknownB") == 1
    assert visible.index("UnknownA") < visible.index("UnknownB")
    assert [call.args[1] for call in case.reaction.call_args_list] == ["fail"]


@pytest.mark.asyncio
async def test_import_preserves_official_alias_name_and_unknown_pool_fallback(ark_gacha_case, mocker):
    from nonebot_plugin_alconna import Match
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.db_handler import get_character_gacha_records

    case = ark_gacha_case
    mocker.patch.object(
        case.command,
        "import_heybox_gacha_data",
        new=mocker.AsyncMock(
            return_value={
                "info": {"uid": "test-role"},
                "data": {"1700000000": {"p": "未收录卡池", "c": [["麒麟X夜刀", 5, True], ["测试干员", 4, False]]}},
            }
        ),
    )

    await case.command.import_handler(
        Match("https://example.com/export", available=True), case.user_session, case.session
    )

    async with get_session() as fresh:
        records = await get_character_gacha_records(case.character_id, fresh)
        assert [
            (record.char_id, record.char_name, record.pool_id, record.pool_name, record.pos) for record in records
        ] == [
            ("char_yato", "麒麟R夜刀", "NORM_1_0_1", "未知寻访", 0),
            ("char_test", "测试干员", "NORM_1_0_1", "未知寻访", 1),
        ]
    assert case.reaction.call_args.args[1] == "done"
