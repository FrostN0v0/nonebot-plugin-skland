from types import SimpleNamespace

import pytest
from sqlalchemy import update, inspect


def _pull(pool_id="standard", *, seq=1, timestamp=1700000000, free=False):
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfCharGachaInfo, EfWeaponGachaInfo

    common = {
        "poolId": pool_id,
        "poolName": pool_id,
        "rarity": 6,
        "isNew": True,
        "gachaTs": str(timestamp * 1000),
        "seqId": str(seq),
    }
    if pool_id.startswith("weapon"):
        return EfWeaponGachaInfo(**common, weaponId="weapon_test", weaponName="测试武器", weaponType="Sword")
    return EfCharGachaInfo(**common, kind="draw", nameText="寻访", charId="char_test", charName="测试干员", isFree=free)


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
            (EndfieldPoolType.WEAPON, "weapon_test"),
        ),
        1,
    ):
        item = _pull(pool_id, seq=seq, free=pool_type == EndfieldPoolType.SPECIAL)
        case.pages[pool_type] = [item, item]

    await case.run()

    records = await get_character_gacha_records(case.character_ids[0], case.session)
    assert {(record.gacha_ts, record.pos) for record in records} == {
        (1600000000, 90),
        *((1700000000, seq) for seq in range(1, 6)),
    }
    assert next(record for record in records if record.pool_id == "special_test").is_free
    assert len(await get_character_gacha_records(case.character_ids[1], case.session)) == 1
    view = case.render.await_args.args[0]
    assert view.record.total_pulls == 6
    assert view.record.joint_total_pulls == 1
    assert view.record.weapon_total_pulls == 1
    assert view.new_count == 4
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
            return SimpleNamespace(gacha_list=[_pull("special_test", seq=2)], hasMore=True)
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
