from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import update, inspect


def _pull(
    pool_id="standard", *, seq=1, timestamp=1700000000, free=False, item_type="char", pool_version=None, rarity=6
):
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfCharGachaInfo, EfWeaponGachaInfo

    common = {
        "poolId": pool_id,
        "poolName": pool_id,
        "rarity": rarity,
        "isNew": True,
        "gachaTs": str(timestamp * 1000),
        "seqId": str(seq),
        "poolVersion": pool_version,
    }
    if item_type == "weapon":
        return EfWeaponGachaInfo(**common, weaponId="weapon_test", weaponName="测试武器", weaponType="Sword")
    return EfCharGachaInfo(**common, kind="draw", nameText="寻访", charId="char_test", charName="测试干员", isFree=free)


def _weapon_api_item(seq: int, *, kind: str = "draw") -> dict:
    if kind == "gift_weapon":
        return {
            "kind": kind,
            "poolId": "weaponbox_1_6_1",
            "poolName": "篆玉申领",
            "poolVersion": None,
            "poolType": "normal",
            "nameText": "玉中身",
            "gachaTs": "1792079999109",
            "seqId": str(seq),
            "giftRewardLabel": "篆玉赠礼",
        }
    return {
        "kind": kind,
        "poolId": "weaponbox_1_6_1",
        "poolName": "篆玉申领",
        "nameText": "测试武器",
        "weaponId": "weapon_test",
        "weaponName": "测试武器",
        "weaponType": "E_WeaponType_Lance",
        "rarity": 4,
        "isNew": False,
        "gachaTs": "1792079999109",
        "seqId": str(seq),
    }


def _malformed_history_response(failure: str, *, is_weapon: bool) -> httpx.Response:
    from nonebot.compat import model_dump

    if failure == "json":
        return httpx.Response(200, text="<html>private-response-content</html>")
    if failure == "encoding":
        return httpx.Response(200, content=b"\xff")
    if failure == "envelope":
        return httpx.Response(200, json=["private-response-content"])
    if failure == "data":
        return httpx.Response(200, json={"code": 0, "data": None})
    item = model_dump(_pull("weapon_test" if is_weapon else "standard", item_type="weapon" if is_weapon else "char"))
    item.pop("weaponId" if is_weapon else "charId")
    item.update(kind="draw", nameText="private-response-content")
    return httpx.Response(200, json={"code": 0, "data": {"list": [item], "hasMore": False}})


@pytest.mark.parametrize("is_weapon", [False, True])
@pytest.mark.parametrize("failure", ["json", "encoding", "envelope", "data", "draw"])
@pytest.mark.asyncio
async def test_ef_history_parse_errors_become_safe_request_errors(app, failure, is_weapon):
    from nonebot_plugin_skland.api import SklandAPI
    from nonebot_plugin_skland.schemas import EndfieldPoolType
    from nonebot_plugin_skland.exception import RequestException

    transport = httpx.MockTransport(lambda request: _malformed_history_response(failure, is_weapon=is_weapon))
    pool_type = EndfieldPoolType.WEAPON if is_weapon else EndfieldPoolType.STANDARD
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(RequestException) as error:
            await SklandAPI.get_ef_gacha_history(pool_type, "1", "private-role-token", client=client)

    assert "private-response-content" not in str(error.value)
    assert "private-role-token" not in str(error.value)


@pytest.mark.parametrize("code", [10000, 10002])
@pytest.mark.asyncio
async def test_ef_history_auth_errors_take_precedence_over_missing_data(app, code):
    from nonebot_plugin_skland.api import SklandAPI
    from nonebot_plugin_skland.schemas import EndfieldPoolType
    from nonebot_plugin_skland.exception import LoginException, UnauthorizedException

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"code": code, "message": "rejected", "data": None})
    )
    error_type = UnauthorizedException if code == 10000 else LoginException
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(error_type):
            await SklandAPI.get_ef_gacha_history(EndfieldPoolType.WEAPON, "1", "private-role-token", client=client)


@pytest.mark.parametrize("legacy_format", [False, True])
def test_weapon_response_ignores_gift_marker_and_preserves_raw_page_boundary(app, legacy_format):
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfWeaponGachaResponse

    draws = [_weapon_api_item(seq) for seq in range(921, 917, -1)]
    if legacy_format:
        for draw in draws:
            draw.pop("kind")
    response = EfWeaponGachaResponse(list=[_weapon_api_item(922, kind="gift_weapon"), *draws], hasMore=True)

    assert [item.seq_id_int for item in response.gacha_list] == [921, 920, 919, 918]
    assert response.next_seq == "918"


def test_character_response_filters_untyped_events_and_preserves_raw_cursor(app):
    from nonebot.compat import model_dump

    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfCharGachaResponse

    response = EfCharGachaResponse(
        list=[
            model_dump(_pull(seq=12)),
            {"kind": "gift", "nameText": "寻访情报书", "seqId": "11"},
            {"nameText": "未标记事件", "seqId": "10"},
        ],
        hasMore=True,
    )

    assert [item.seq_id_int for item in response.gacha_list] == [12]
    assert response.next_seq == "10"


@pytest.mark.asyncio
async def test_weapon_pagination_preserves_raw_cursor_after_gift_filter(app, mocker):
    import nonebot_plugin_skland.services.gacha as service
    from nonebot_plugin_skland.schemas import EndfieldPoolType
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfWeaponGachaResponse

    pages = {
        None: EfWeaponGachaResponse(
            list=[_weapon_api_item(922, kind="gift_weapon"), *[_weapon_api_item(seq) for seq in range(921, 917, -1)]],
            hasMore=True,
        ),
        "918": EfWeaponGachaResponse(
            list=[_weapon_api_item(seq) for seq in range(917, 912, -1)],
            hasMore=False,
        ),
    }
    calls = []

    async def fetch(pool_type, server_id, role_token, seq_id=None, client=None):
        calls.append(seq_id)
        return pages[seq_id]

    mocker.patch.object(service.SklandAPI, "get_ef_gacha_history", side_effect=fetch)

    records = await service.get_all_ef_gacha_records("1", EndfieldPoolType.WEAPON, "role-token")

    assert calls == [None, "918"]
    assert [record.seq_id_int for record in records] == list(range(921, 912, -1))


async def _save_pull(session, character_id, pull):
    from nonebot_plugin_skland.model import GachaRecord

    session.add(
        GachaRecord(
            character_id=character_id,
            pool_id=pull.poolId,
            pool_name=pull.poolName,
            item_type=pull.item_type,
            char_id=pull.item_id,
            char_name=pull.item_name,
            rarity=pull.rarity,
            is_new=pull.isNew,
            is_free=pull.is_free_pull,
            gacha_ts=pull.gacha_ts_sec,
            pos=pull.seq_id_int,
        )
    )
    await session.commit()


@pytest.fixture
async def gacha_case(app, mocker, make_user_session):
    from nonebot_plugin_alconna import Match
    from nonebot_plugin_orm import get_session

    import nonebot_plugin_skland.services.gacha as service
    from nonebot_plugin_skland.model import SkUser, Character
    import nonebot_plugin_skland.commands.endfield.gacha as command
    from nonebot_plugin_skland.db_handler import set_default_character

    async with get_session() as session:
        account_ids, character_ids = [], []
        for index in range(2):
            account = SkUser(
                owner_id=901,
                skland_user_id=f"remote-{index}",
                access_token=f"private-access-{index}",
                cred=f"private-cred-{index}",
                cred_token=f"private-token-{index}",
            )
            session.add(account)
            await session.flush()
            character = Character(
                account_id=account.id,
                uid=f"binding-{index}",
                role_id=f"role-{index}",
                app_code="endfield",
                channel_master_id="1",
                server_name="China",
                nickname=f"管理员{index}",
                level=10,
                is_skland_default=False,
            )
            session.add(character)
            await session.flush()
            account_ids.append(account.id)
            character_ids.append(character.id)
        await set_default_character(901, "endfield", character_ids[0], session)
        user_session = await make_user_session(session, 901)
        # Exercise the production hazard even when the configured session keeps values alive.
        session.sync_session.expire_on_commit = True
        pages, messages = {}, []

        async def fetch(pool_type, server_id, role_token, seq_id=None, client=None):
            return SimpleNamespace(gacha_list=pages.get(pool_type, []), hasMore=False)

        async def send(message, **kwargs):
            messages.append(message)

        fetch_mock = mocker.patch.object(service.SklandAPI, "get_ef_gacha_history", side_effect=fetch)
        grant_mock = mocker.patch.object(service.SklandLoginAPI, "get_grant_code", return_value="private-grant")
        role_mock = mocker.patch.object(
            service.SklandLoginAPI, "get_role_token_by_uid", return_value="private-role-token"
        )
        profile_mock = mocker.patch.object(
            command.SklandAPI, "endfield_card", return_value=SimpleNamespace(base=SimpleNamespace(avatarUrl=""))
        )
        mocker.patch.object(
            command.SklandAPI,
            "get_ef_gacha_content",
            return_value=SimpleNamespace(
                pool=SimpleNamespace(
                    up_six_char_ids=["char_test"], up6_image="", rotate_image="", up_six_display_name="测试"
                )
            ),
        )
        render_mock = mocker.patch.object(command, "render_ef_gacha_history", return_value=[b"image"])
        send_mock = mocker.patch.object(command.UniMessage, "send", new=send)
        reaction_mock = mocker.patch.object(command, "send_reaction")

        async def run(*, role_index=None, begin=None, limit=None):
            if inspect(user_session.user).expired:
                await session.refresh(user_session.user)
            await command.ef_gacha_history_handler(
                user_session,
                session,
                Match(begin, available=begin is not None),
                Match(limit, available=limit is not None),
                Match(None, available=False),
                SimpleNamespace(self_id="bot"),
                role_index=role_index,
            )

        yield SimpleNamespace(
            session=session,
            user_session=user_session,
            account_ids=account_ids,
            character_ids=character_ids,
            pages=pages,
            messages=messages,
            fetch=fetch_mock,
            grant=grant_mock,
            role_token=role_mock,
            profile=profile_mock,
            render=render_mock,
            send=send_mock,
            reaction=reaction_mock,
            run=run,
            command=command,
        )


@pytest.mark.asyncio
async def test_default_query_fetches_all_categories_and_deduplicates_role_history(gacha_case):
    from nonebot_plugin_skland.schemas import EndfieldPoolType
    from nonebot_plugin_skland.db_handler import get_character_gacha_records

    case = gacha_case
    old = _pull(seq=90, timestamp=1600000000)
    existing = _pull(seq=1)
    await _save_pull(case.session, case.character_ids[0], old)
    await _save_pull(case.session, case.character_ids[0], existing)
    await _save_pull(case.session, case.character_ids[1], existing)
    for seq, (pool_type, pool_id) in enumerate(
        (
            (EndfieldPoolType.STANDARD, "standard"),
            (EndfieldPoolType.SPECIAL, "special_test"),
            (EndfieldPoolType.BEGINNER, "beginner"),
            (EndfieldPoolType.JOINT, "joint_test"),
            (EndfieldPoolType.RERUN, "rerun_chr_test"),
            (EndfieldPoolType.WEAPON, "weapon_test"),
        ),
        1,
    ):
        item = _pull(
            pool_id,
            seq=seq,
            free=pool_type == EndfieldPoolType.SPECIAL,
            item_type="weapon" if pool_type == EndfieldPoolType.WEAPON else "char",
            pool_version=1 if pool_type == EndfieldPoolType.RERUN else None,
        )
        case.pages[pool_type] = [item, item]

    await case.run()

    records = await get_character_gacha_records(case.character_ids[0], case.session)
    assert {(record.gacha_ts, record.pos) for record in records} == {
        (1600000000, 90),
        *((1700000000, seq) for seq in range(1, 7)),
    }
    assert next(record for record in records if record.pool_id == "special_test").is_free
    assert len(await get_character_gacha_records(case.character_ids[1], case.session)) == 1
    view = case.render.await_args.args[0]
    assert view.record.total_pulls == 7
    assert view.record.rerun_total_pulls == 1
    assert view.record.joint_total_pulls == 1
    assert view.record.weapon_total_pulls == 1
    assert view.new_count == 5
    assert not view.is_cached
    assert view.role_id == "role-0"


@pytest.mark.asyncio
async def test_selected_account_history_commits_before_renderer_failure(gacha_case):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.schemas import EndfieldPoolType
    from nonebot_plugin_skland.db_handler import get_default_character, get_character_gacha_records

    case = gacha_case
    case.pages[EndfieldPoolType.STANDARD] = [_pull()]
    case.render.side_effect = RuntimeError("renderer unavailable")

    with pytest.raises(RuntimeError, match="renderer unavailable"):
        await case.run(role_index=2)

    async with get_session() as fresh:
        records = await get_character_gacha_records(case.character_ids[1], fresh)
        assert [(record.char_id, record.pos) for record in records] == [("char_test", 1)]
        assert await get_character_gacha_records(case.character_ids[0], fresh) == []
        assert (await get_default_character(901, "endfield", fresh)).id == case.character_ids[0]
    case.grant.assert_awaited_once_with("private-access-1", 1)
    case.role_token.assert_awaited_once_with("binding-1", "private-grant")
    assert case.messages == []
    assert "done" not in [call.args[1] for call in case.reaction.call_args_list]


@pytest.mark.parametrize("failure", ["missing_token", "api_error"])
@pytest.mark.parametrize("has_cache", [False, True])
@pytest.mark.asyncio
async def test_sync_failure_uses_only_marked_cache_or_reports_cause(gacha_case, failure, has_cache):
    from nonebot_plugin_skland.model import SkUser
    from nonebot_plugin_skland.exception import RequestException

    case = gacha_case
    if has_cache:
        await _save_pull(case.session, case.character_ids[0], _pull())
    if failure == "missing_token":
        await case.session.execute(update(SkUser).where(SkUser.id == case.account_ids[0]).values(access_token=None))
        await case.session.commit()
        cause = "未保存 token"
    else:
        case.grant.side_effect = RequestException("GET https://example.com/history?token=private-role-token")
        cause = "同步失败"

    await case.run()

    if has_cache:
        view = case.render.await_args.args[0]
        assert view.is_cached
        assert cause in view.notice
        assert "本地缓存" in view.notice
        assert view.new_count == 0
        assert view.record.total_pulls == 1
    else:
        case.render.assert_not_awaited()
        assert cause in case.messages[0].extract_plain_text()
        assert "done" not in [call.args[1] for call in case.reaction.call_args_list]
    visible = " ".join(message.extract_plain_text() for message in case.messages)
    if has_cache:
        visible += case.render.await_args.args[0].model_dump_json()
    assert "private-access" not in visible
    assert "private-cred" not in visible
    assert "private-token" not in visible
    assert "private-role-token" not in visible


@pytest.mark.parametrize("has_cache", [False, True])
@pytest.mark.parametrize("failure_page", ["first", "later"])
@pytest.mark.parametrize("failure", ["json", "draw"])
@pytest.mark.asyncio
async def test_malformed_history_page_reports_failure_without_partial_writes(
    gacha_case, mocker, has_cache, failure_page, failure
):
    from nonebot.compat import model_dump

    from nonebot_plugin_skland.schemas import EndfieldPoolType
    from nonebot_plugin_skland.db_handler import get_character_gacha_records

    case = gacha_case
    if has_cache:
        await _save_pull(case.session, case.character_ids[0], _pull(seq=90, timestamp=1600000000))

    def respond(request):
        if request.url.path.endswith("/char"):
            records = (
                [model_dump(_pull(seq=1))] if request.url.params["pool_type"] == EndfieldPoolType.STANDARD.value else []
            )
            return httpx.Response(200, json={"code": 0, "data": {"list": records, "hasMore": False}})
        assert request.url.path.endswith("/weapon")
        if failure_page == "later" and "seq_id" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "list": [model_dump(_pull("weapon_test", seq=2, item_type="weapon"))],
                        "hasMore": True,
                    },
                },
            )
        return _malformed_history_response(failure, is_weapon=True)

    # Restore the actual API parser; only HTTP transport is replaced.
    mocker.stop(case.fetch)
    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    mocker.patch.object(httpx, "AsyncClient", side_effect=lambda **kwargs: client_type(transport=transport, **kwargs))

    await case.run()

    records = await get_character_gacha_records(case.character_ids[0], case.session)
    assert [(record.gacha_ts, record.pos) for record in records] == ([(1600000000, 90)] if has_cache else [])
    assert len(case.messages) == 1
    visible = case.messages[0].extract_plain_text()
    if has_cache:
        view = case.render.await_args.args[0]
        assert view.is_cached
        assert view.new_count == 0
        assert view.record.total_pulls == 1
        assert "同步失败" in view.notice
        assert "本地缓存" in view.notice
        assert case.reaction.call_args.args[1] == "done"
        visible += view.notice
    else:
        case.render.assert_not_awaited()
        assert "同步失败" in visible
        assert "done" not in [call.args[1] for call in case.reaction.call_args_list]
    assert "private-response-content" not in visible
    assert "private-role-token" not in visible


@pytest.mark.parametrize("has_cache", [False, True])
@pytest.mark.asyncio
async def test_later_page_failure_does_not_save_partial_categories(gacha_case, has_cache):
    from nonebot_plugin_skland.schemas import EndfieldPoolType
    from nonebot_plugin_skland.exception import RequestException
    from nonebot_plugin_skland.db_handler import get_character_gacha_records

    case = gacha_case
    if has_cache:
        await _save_pull(case.session, case.character_ids[0], _pull(seq=90, timestamp=1600000000))

    async def fetch(pool_type, server_id, role_token, seq_id=None, client=None):
        if pool_type == EndfieldPoolType.STANDARD:
            return SimpleNamespace(gacha_list=[_pull(seq=1)], hasMore=False)
        if seq_id is None:
            return SimpleNamespace(gacha_list=[_pull("special_test", seq=2)], hasMore=True, next_seq="2")
        raise RequestException("后续分页失败")

    case.fetch.side_effect = fetch
    await case.run()

    records = await get_character_gacha_records(case.character_ids[0], case.session)
    assert [(record.gacha_ts, record.pos) for record in records] == ([(1600000000, 90)] if has_cache else [])
    if has_cache:
        view = case.render.await_args.args[0]
        assert view.is_cached
        assert view.record.total_pulls == 1
        assert view.new_count == 0
    else:
        case.render.assert_not_awaited()
        assert "同步失败" in case.messages[0].extract_plain_text()


@pytest.mark.asyncio
async def test_profile_refresh_is_saved_even_if_profile_retry_fails(gacha_case, mocker):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.model import SkUser
    from nonebot_plugin_skland.schemas import EndfieldPoolType
    from nonebot_plugin_skland.services.auth import SklandLoginAPI
    from nonebot_plugin_skland.db_handler import get_character_gacha_records
    from nonebot_plugin_skland.exception import RequestException, UnauthorizedException

    case = gacha_case
    case.pages[EndfieldPoolType.STANDARD] = [_pull()]
    case.profile.side_effect = [UnauthorizedException("expired"), RequestException("profile unavailable")]
    mocker.patch.object(SklandLoginAPI, "refresh_token", return_value="refreshed-private-token")

    await case.run()

    view = case.render.await_args.args[0]
    assert view.avatar_url == ""
    assert view.record.total_pulls == 1
    assert not view.is_cached
    async with get_session() as fresh:
        assert (await fresh.get(SkUser, case.account_ids[0])).cred_token == "refreshed-private-token"
        assert (await fresh.get(SkUser, case.account_ids[1])).cred_token == "private-token-1"
        assert len(await get_character_gacha_records(case.character_ids[0], fresh)) == 1
    assert case.messages[0].extract_plain_text() == ""


@pytest.mark.parametrize("platform", ["QQClient", "Telegram"])
@pytest.mark.asyncio
async def test_paged_delivery_preserves_page_order(gacha_case, platform):
    from nonebot_plugin_alconna import Image, Reference

    from nonebot_plugin_skland.schemas import EndfieldPoolType

    case = gacha_case
    case.user_session.session.scope = platform
    case.pages[EndfieldPoolType.STANDARD] = [_pull()]
    case.render.return_value = [b"page-one", b"page-two", b"page-three"]

    await case.run()

    if platform == "QQClient":
        assert len(case.messages) == 1
        delivered = [node.content[Image][0].raw for node in case.messages[0][Reference][0].children]
    else:
        delivered = [message[Image][0].raw for message in case.messages]
    assert delivered == [b"page-one", b"page-two", b"page-three"]
    assert case.reaction.call_args.args[1] == "done"


@pytest.mark.asyncio
async def test_page_send_failure_does_not_mark_done_or_lose_history(gacha_case, mocker):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.schemas import EndfieldPoolType
    from nonebot_plugin_skland.db_handler import get_character_gacha_records

    case = gacha_case
    case.user_session.session.scope = "Telegram"
    case.pages[EndfieldPoolType.STANDARD] = [_pull()]
    case.render.return_value = [b"first", b"second", b"third"]
    sent = []

    async def send(message, **kwargs):
        sent.append(message)
        if len(sent) == 2:
            raise RuntimeError("delivery unavailable")

    mocker.patch.object(case.command.UniMessage, "send", new=send)
    with pytest.raises(RuntimeError, match="delivery unavailable"):
        await case.run()

    assert len(sent) == 2
    assert "done" not in [call.args[1] for call in case.reaction.call_args_list]
    async with get_session() as fresh:
        assert len(await get_character_gacha_records(case.character_ids[0], fresh)) == 1


@pytest.mark.asyncio
async def test_sparse_rerun_pages_follow_raw_cursor_through_reward_only_page(app, mocker):
    from nonebot.compat import model_dump

    import nonebot_plugin_skland.services.gacha as service
    from nonebot_plugin_skland.schemas import EndfieldPoolType

    first = model_dump(_pull("rerun_chr_yvonne", seq=1283, pool_version=1))
    last = [model_dump(_pull("rerun_chr_yvonne", seq=seq, pool_version=1)) for seq in (42, 41)]
    pages = {
        None: {"list": [first, {"kind": "gift_intel_book", "seqId": "1282"}], "hasMore": True},
        "1282": {"list": [{"kind": "gift_intel_book", "seqId": "1266"}], "hasMore": True},
        "1266": {"list": last, "hasMore": False},
    }
    cursors = []

    def respond(request):
        assert request.url.path == "/api/record/char"
        assert request.url.params["pool_type"] == "E_CharacterGachaPoolType_Rerun"
        cursor = request.url.params.get("seq_id")
        cursors.append(cursor)
        return httpx.Response(200, json={"code": 0, "data": pages[cursor]})

    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    mocker.patch.object(httpx, "AsyncClient", side_effect=lambda **kwargs: client_type(transport=transport, **kwargs))

    records = await service.get_all_ef_gacha_records("1", EndfieldPoolType.RERUN, "test-role-token")

    assert [item.seq_id_int for item in records] == [1283, 42, 41]
    assert all(item.poolVersion == 1 for item in records)
    assert cursors == [None, "1282", "1266"]


@pytest.mark.parametrize("next_cursor", [None, "10", "11"])
@pytest.mark.asyncio
async def test_unusable_rerun_cursor_fails_instead_of_saving_partial_history(app, mocker, next_cursor):
    from nonebot.compat import model_dump

    import nonebot_plugin_skland.services.gacha as service
    from nonebot_plugin_skland.schemas import EndfieldPoolType
    from nonebot_plugin_skland.exception import RequestException

    def respond(request):
        if "seq_id" not in request.url.params:
            items = [model_dump(_pull("rerun_chr_yvonne", seq=10, pool_version=1))]
        else:
            items = [{"kind": "gift", "seqId": next_cursor}] if next_cursor is not None else []
        return httpx.Response(200, json={"code": 0, "data": {"list": items, "hasMore": True}})

    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    mocker.patch.object(httpx, "AsyncClient", side_effect=lambda **kwargs: client_type(transport=transport, **kwargs))
    with pytest.raises(RequestException):
        await service.get_all_ef_gacha_records("1", EndfieldPoolType.RERUN, "test-role-token")


@pytest.mark.asyncio
async def test_rerun_sync_reclassifies_cached_weapon_and_backfills_period_without_duplicates(gacha_case):
    from nonebot_plugin_skland.schemas import EndfieldPoolType
    from nonebot_plugin_skland.db_handler import get_character_gacha_records

    case = gacha_case
    legacy_weapon = _pull("rerun_wpn_yvonne", seq=20, item_type="weapon", rarity=4)
    await _save_pull(case.session, case.character_ids[0], legacy_weapon)
    await _save_pull(case.session, case.character_ids[1], legacy_weapon)
    case.pages[EndfieldPoolType.RERUN] = [
        _pull(
            "rerun_chr_yvonne",
            seq=seq,
            timestamp=1700000010 + (seq - 100) // 10,
            free=seq >= 130,
            pool_version=1,
            rarity=4,
        )
        for seq in range(100, 140)
    ]
    case.pages[EndfieldPoolType.WEAPON] = [
        _pull("rerun_wpn_yvonne", seq=seq, item_type="weapon", pool_version=1, rarity=4) for seq in range(11, 21)
    ]

    await case.run()

    records = await get_character_gacha_records(case.character_ids[0], case.session)
    assert len(records) == 50
    assert all(record.pool_version == 1 for record in records)
    assert len([record for record in records if record.pos == 20]) == 1
    other = await get_character_gacha_records(case.character_ids[1], case.session)
    assert len(other) == 1
    assert other[0].pool_version is None
    view = case.render.await_args.args[0]
    assert (view.record.total_pulls, view.record.char_total_pulls, view.record.weapon_total_pulls) == (50, 40, 10)
    assert not view.record.standard_pools
    assert view.record.rerun_pools[0].up_six_chars == ["char_test"]
    assert view.new_count == 49
    rerun = next(category for category in view.categories if category.key == "rerun").pools[0]
    assert rerun.rerun_progress.paid_count == 30
    assert rerun.rerun_progress.free_ten_pulls_unlocked == 1

    await case.run()

    assert case.render.await_args.args[0].new_count == 0
    assert len(await get_character_gacha_records(case.character_ids[0], case.session)) == 50


@pytest.mark.asyncio
async def test_failed_rerun_page_does_not_commit_other_categories_or_period_backfill(gacha_case, mocker):
    from nonebot.compat import model_dump

    from nonebot_plugin_skland.schemas import EndfieldPoolType
    from nonebot_plugin_skland.db_handler import get_character_gacha_records

    case = gacha_case
    old = _pull("rerun_wpn_yvonne", seq=80, item_type="weapon")
    await _save_pull(case.session, case.character_ids[0], old)

    def respond(request):
        if request.url.path.endswith("/weapon"):
            items = [model_dump(_pull("rerun_wpn_yvonne", seq=80, item_type="weapon", pool_version=1))]
        elif request.url.params["pool_type"] == EndfieldPoolType.RERUN.value:
            if "seq_id" in request.url.params:
                return httpx.Response(200, text="invalid response")
            return httpx.Response(
                200,
                json={"code": 0, "data": {"list": [model_dump(_pull("rerun_chr_yvonne", seq=2))], "hasMore": True}},
            )
        elif request.url.params["pool_type"] == EndfieldPoolType.STANDARD.value:
            items = [model_dump(_pull(seq=1))]
        else:
            items = []
        return httpx.Response(200, json={"code": 0, "data": {"list": items, "hasMore": False}})

    mocker.stop(case.fetch)
    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    mocker.patch.object(httpx, "AsyncClient", side_effect=lambda **kwargs: client_type(transport=transport, **kwargs))

    await case.run()

    records = await get_character_gacha_records(case.character_ids[0], case.session)
    assert [(record.pool_id, record.pos, record.pool_version) for record in records] == [("rerun_wpn_yvonne", 80, None)]
    view = case.render.await_args.args[0]
    assert view.is_cached
    assert view.new_count == 0
    assert view.record.char_total_pulls == 0
    assert view.record.weapon_total_pulls == 1
