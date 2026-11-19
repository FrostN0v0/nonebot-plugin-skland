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
    from nonebot_plugin_skland.player_data import ArkCardDataSource
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
        full_card = mocker.AsyncMock(side_effect=AssertionError("gacha must not load an ArkCard"))
        mocker.patch.object(command, "ark_card_data", ArkCardDataSource(ttl=60, max_entries=8, loader=full_card))
        avatar_mock = mocker.patch.object(
            command.SklandAPI, "ark_avatar", new=mocker.AsyncMock(return_value="https://example.com/avatar.png")
        )
        render_mock = mocker.patch.object(command, "render_gacha_history", new=mocker.AsyncMock(return_value=tiny_png))
        mocker.patch.object(command.UniMessage, "send", new=send)
        reaction_mock = mocker.patch.object(command, "send_reaction")

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
            avatar=avatar_mock,
            full_card=full_card,
            render=render_mock,
            reaction=reaction_mock,
            run=run,
        )


@pytest.mark.parametrize("platform", ["QQClient", "Discord"])
@pytest.mark.parametrize(("begin", "limit"), [(2, 10), (2, None), (-9, -1), (-4, None), (2, 4), (9, 4)])
@pytest.mark.asyncio
async def test_pool_slice_renders_each_selected_pool_once(ark_gacha_case, mocker, tiny_png, platform, begin, limit):
    from nonebot_plugin_skland.schemas import CRED

    case = ark_gacha_case
    case.pulls.extend(_pull(index) for index in range(11))
    mocker.patch.object(type(case.user_session), "platform", new_callable=mocker.PropertyMock, return_value=platform)
    node_mock = mocker.patch.object(case.command, "CustomNode", wraps=case.command.CustomNode)
    rendered_bounds, rendered_pools = [], []

    async def render(record, *, nickname, channel_master_id, avatar_url, level, begin, limit):
        assert nickname == "博士"
        assert channel_master_id == "1"
        assert avatar_url == "https://example.com/avatar.png"
        assert level is None
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
    case.avatar.assert_awaited_once_with(CRED("test-cred", "test-token"), uid="test-role")
    case.full_card.assert_not_awaited()
    assert all(page_stop <= stop for _, page_stop in rendered_bounds)
    if platform == "QQClient" and stop - start > 3:
        assert [call.args[1] for call in node_mock.call_args_list] == [
            f"博士 | {page_start}-{page_stop}" for page_start, page_stop in expected_bounds
        ]
    assert case.reaction.call_args.args[1] == "done"


@pytest.mark.parametrize("failure", ["avatar_unavailable", "avatar_expired", "avatar_unexpected", "render", "send"])
@pytest.mark.asyncio
async def test_fetched_records_and_refreshed_credentials_survive_presentation_failure(ark_gacha_case, mocker, failure):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.model import SkUser
    from nonebot_plugin_skland.schemas import CRED
    from nonebot_plugin_skland.db_handler import get_character_gacha_records
    from nonebot_plugin_skland.exception import LoginException, RequestException

    case = ark_gacha_case
    case.pulls.append(_pull())
    refreshed = CRED("refreshed-cred", "refreshed-token")
    get_cred = mocker.patch.object(
        case.command.SklandLoginAPI, "get_cred", new=mocker.AsyncMock(return_value=refreshed)
    )

    async def avatar(cred, *, uid):
        if cred.token == "test-token" or failure == "avatar_expired":
            raise LoginException("expired credentials")
        if failure == "avatar_unavailable":
            raise RequestException("avatar unavailable")
        if failure == "avatar_unexpected":
            raise ValueError("avatar response changed")
        return "https://example.com/avatar.png"

    case.avatar.side_effect = avatar
    if failure in {"avatar_unavailable", "avatar_expired"}:
        await case.run()
        case.render.assert_awaited_once()
        assert case.render.await_args.kwargs["avatar_url"] is None
        assert len(case.messages) == 1
    elif failure == "avatar_unexpected":
        with pytest.raises(ValueError, match="avatar response changed"):
            await case.run()
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

    get_cred.assert_awaited_once_with("test-grant")
    assert case.avatar.await_args_list == [
        mocker.call(CRED("test-cred", "test-token"), uid="test-role"),
        mocker.call(refreshed, uid="test-role"),
    ]
    case.full_card.assert_not_awaited()

    await case.session.rollback()
    async with get_session() as fresh:
        records = await get_character_gacha_records(case.character_id, fresh)
        assert [(record.pool_id, record.char_id, record.gacha_ts, record.pos) for record in records] == [
            ("pool-0", "char_test", 1700000000, 0)
        ]
        account = await fresh.get(SkUser, case.account_id)
        assert (account.cred, account.cred_token) == ("refreshed-cred", "refreshed-token")
    expected_reactions = (
        ["processing", "done"] if failure in {"avatar_unavailable", "avatar_expired"} else ["processing"]
    )
    assert [call.args[1] for call in case.reaction.call_args_list] == expected_reactions


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
