"""Behavior tests for short-lived ArkCard caching."""

import asyncio
from typing import Any

import pytest


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.mark.asyncio
async def test_ark_card_data_source_reuses_value_until_ttl(app, mocker):
    from nonebot_plugin_skland.player_data import ArkCardDataSource

    clock = FakeClock()
    calls = 0
    values = [object(), object()]

    async def load(_user, _character) -> Any:
        nonlocal calls
        value = values[calls]
        calls += 1
        return value

    source = ArkCardDataSource(ttl=120, max_entries=64, loader=load, clock=clock)
    user = mocker.Mock(id=1, user_id="account-1")
    character = mocker.Mock(
        app_code="arknights",
        channel_master_id="server-1",
        uid="role-1",
        role_id="role-id-1",
    )

    first = await source.get(user, character)
    clock.advance(119)
    cached = await source.get(user, character)
    clock.advance(1)
    refreshed = await source.get(user, character)

    assert first is values[0]
    assert cached is first
    assert refreshed is values[1]
    assert calls == 2


@pytest.mark.asyncio
async def test_ark_card_data_source_recovers_after_loader_error(app, mocker):
    from nonebot_plugin_skland.player_data import ArkCardDataSource

    calls = 0
    value = object()

    async def load(_user, _character) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("load failed")
        return value

    source = ArkCardDataSource(ttl=120, max_entries=64, loader=load)
    user = mocker.Mock(id=1, user_id="account-1")
    character = mocker.Mock(
        app_code="arknights",
        channel_master_id="server-1",
        uid="role-1",
        role_id="role-id-1",
    )

    with pytest.raises(RuntimeError, match="load failed"):
        await source.get(user, character)

    recovered = await source.get(user, character)
    cached = await source.get(user, character)

    assert recovered is value
    assert cached is recovered
    assert calls == 2


@pytest.mark.asyncio
async def test_ark_card_data_source_merges_concurrent_requests(app, mocker):
    from nonebot_plugin_skland.player_data import ArkCardDataSource

    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0
    value = object()

    async def load(_user, _character) -> Any:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return value

    source = ArkCardDataSource(ttl=120, max_entries=64, loader=load)
    user = mocker.Mock(id=1, user_id="account-1")
    character = mocker.Mock(
        app_code="arknights",
        channel_master_id="server-1",
        uid="role-1",
        role_id="role-id-1",
    )

    requests = [asyncio.create_task(source.get(user, character)) for _ in range(5)]
    await started.wait()
    await asyncio.sleep(0)
    release.set()
    results = await asyncio.gather(*requests)

    assert results == [value] * 5
    assert calls == 1


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_cancel_shared_load(app, mocker):
    from nonebot_plugin_skland.player_data import ArkCardDataSource

    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0
    value = object()

    async def load(_user, _character) -> Any:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return value

    source = ArkCardDataSource(ttl=120, max_entries=64, loader=load)
    user = mocker.Mock(id=1, user_id="account-1")
    character = mocker.Mock(
        app_code="arknights",
        channel_master_id="server-1",
        uid="role-1",
        role_id="role-id-1",
    )

    cancelled_request = asyncio.create_task(source.get(user, character))
    await started.wait()
    cancelled_request.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled_request

    remaining_request = asyncio.create_task(source.get(user, character))
    release.set()

    assert await remaining_request is value
    assert calls == 1


@pytest.mark.asyncio
async def test_ark_card_data_source_invalidates_user_cache(app, mocker):
    from nonebot_plugin_skland.player_data import ArkCardDataSource

    calls = 0
    values = [object(), object()]

    async def load(_user, _character) -> Any:
        nonlocal calls
        value = values[calls]
        calls += 1
        return value

    source = ArkCardDataSource(ttl=120, max_entries=64, loader=load)
    user = mocker.Mock(id=1, user_id="account-1")
    character = mocker.Mock(
        app_code="arknights",
        channel_master_id="server-1",
        uid="role-1",
        role_id="role-id-1",
    )

    first = await source.get(user, character)
    await source.invalidate_user(user.id)
    assert user.id not in source._generations
    refreshed = await source.get(user, character)

    assert first is values[0]
    assert refreshed is values[1]
    assert calls == 2


@pytest.mark.asyncio
async def test_ark_card_data_source_does_not_cache_none(app, mocker):
    from nonebot_plugin_skland.player_data import ArkCardDataSource

    calls = 0
    value = object()

    async def load(_user, _character) -> Any:
        nonlocal calls
        calls += 1
        return None if calls == 1 else value

    source = ArkCardDataSource(ttl=120, max_entries=64, loader=load)
    user = mocker.Mock(id=1, user_id="account-1")
    character = mocker.Mock(
        app_code="arknights",
        channel_master_id="server-1",
        uid="role-1",
        role_id="role-id-1",
    )

    assert await source.get(user, character) is None
    assert await source.get(user, character) is value
    assert calls == 2


@pytest.mark.parametrize(
    ("target", "field", "changed"),
    [
        ("user", "id", 2),
        ("user", "user_id", "account-2"),
        ("character", "app_code", "endfield"),
        ("character", "channel_master_id", "server-2"),
        ("character", "uid", "role-2"),
        ("character", "role_id", "role-id-2"),
    ],
)
@pytest.mark.asyncio
async def test_ark_card_data_source_uses_full_role_identity(app, mocker, target, field, changed):
    from nonebot_plugin_skland.player_data import ArkCardDataSource

    calls = 0

    async def load(_user, _character) -> Any:
        nonlocal calls
        calls += 1
        return object()

    source = ArkCardDataSource(ttl=120, max_entries=64, loader=load)
    user_data = {"id": 1, "user_id": "account-1"}
    character_data = {
        "app_code": "arknights",
        "channel_master_id": "server-1",
        "uid": "role-1",
        "role_id": "role-id-1",
    }
    first_user = mocker.Mock(**user_data)
    first_character = mocker.Mock(**character_data)
    if target == "user":
        user_data[field] = changed
    else:
        character_data[field] = changed

    await source.get(first_user, first_character)
    await source.get(mocker.Mock(**user_data), mocker.Mock(**character_data))

    assert calls == 2


@pytest.mark.asyncio
async def test_ark_card_data_source_evicts_least_recently_used_role(app, mocker):
    from nonebot_plugin_skland.player_data import ArkCardDataSource

    loaded_uids: list[str] = []

    async def load(_user, character) -> Any:
        loaded_uids.append(character.uid)
        return object()

    source = ArkCardDataSource(ttl=120, max_entries=2, loader=load)
    user = mocker.Mock(id=1, user_id="account-1")

    def character(uid: str):
        return mocker.Mock(
            app_code="arknights",
            channel_master_id="server-1",
            uid=uid,
            role_id=f"role-id-{uid}",
        )

    first = character("role-1")
    second = character("role-2")
    third = character("role-3")

    await source.get(user, first)
    await source.get(user, second)
    await source.get(user, first)
    await source.get(user, third)
    await source.get(user, first)
    await source.get(user, second)

    assert loaded_uids == ["role-1", "role-2", "role-3", "role-2"]


@pytest.mark.asyncio
async def test_expired_entry_is_purged_before_lru_eviction(app, mocker):
    from nonebot_plugin_skland.player_data import ArkCardDataSource

    clock = FakeClock()
    loaded_uids: list[str] = []

    async def load(_user, character) -> Any:
        loaded_uids.append(character.uid)
        return object()

    source = ArkCardDataSource(ttl=10, max_entries=2, loader=load, clock=clock)
    user = mocker.Mock(id=1, user_id="account-1")

    def character(uid: str):
        return mocker.Mock(
            app_code="arknights",
            channel_master_id="server-1",
            uid=uid,
            role_id=f"role-id-{uid}",
        )

    first = character("role-1")
    second = character("role-2")
    third = character("role-3")

    await source.get(user, first)
    clock.advance(5)
    await source.get(user, second)
    clock.advance(4)
    await source.get(user, first)
    clock.advance(2)
    await source.get(user, third)
    await source.get(user, second)

    assert loaded_uids == ["role-1", "role-2", "role-3"]


@pytest.mark.asyncio
async def test_invalidated_inflight_result_is_not_cached(app, mocker):
    from nonebot_plugin_skland.player_data import ArkCardDataSource

    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0
    values = [object(), object()]

    async def load(_user, _character) -> Any:
        nonlocal calls
        value = values[calls]
        calls += 1
        if calls == 1:
            started.set()
            await release.wait()
        return value

    source = ArkCardDataSource(ttl=120, max_entries=64, loader=load)
    user = mocker.Mock(id=1, user_id="account-1")
    character = mocker.Mock(
        app_code="arknights",
        channel_master_id="server-1",
        uid="role-1",
        role_id="role-id-1",
    )

    first_request = asyncio.create_task(source.get(user, character))
    await started.wait()
    await source.invalidate_user(user.id)
    assert source._generations[user.id] == 1
    release.set()

    assert await first_request is values[0]
    assert user.id not in source._generations
    assert await source.get(user, character) is values[1]
    assert calls == 2


@pytest.mark.asyncio
async def test_shared_ark_card_data_source_uses_user_credentials(app, mocker):
    from nonebot_plugin_skland.player_data import get_ark_card, ark_card_data

    value = object()
    fetch = mocker.patch(
        "nonebot_plugin_skland.player_data.SklandAPI.ark_card",
        new=mocker.AsyncMock(return_value=value),
    )
    user = mocker.Mock(
        id=99,
        user_id="account-99",
        access_token="access-token",
        cred="cred-value",
        cred_token="cred-token-value",
    )
    character = mocker.Mock(
        app_code="arknights",
        channel_master_id="server-1",
        uid="role-99",
        role_id="role-id-99",
    )
    await ark_card_data.invalidate_user(user.id)

    result = await get_ark_card(user, character)

    assert result is value
    cred, uid = fetch.await_args.args
    assert cred.cred == "cred-value"
    assert cred.token == "cred-token-value"
    assert uid == "role-99"
    await ark_card_data.invalidate_user(user.id)


@pytest.mark.asyncio
async def test_get_ark_card_refreshes_each_waiter_context(app, mocker):
    from nonebot_plugin_skland.api import SklandLoginAPI
    from nonebot_plugin_skland.exception import UnauthorizedException
    from nonebot_plugin_skland.player_data import get_ark_card, ark_card_data

    value = object()

    async def get(user, _character) -> Any:
        if user.cred_token == "expired-token":
            raise UnauthorizedException
        return value

    get_card = mocker.patch.object(ark_card_data, "get", new=mocker.AsyncMock(side_effect=get))
    refresh = mocker.patch.object(
        SklandLoginAPI,
        "refresh_token",
        new=mocker.AsyncMock(return_value="fresh-token"),
    )
    users = [mocker.Mock(cred="cred-value", cred_token="expired-token") for _ in range(2)]
    character = mocker.Mock()

    results = await asyncio.gather(*(get_ark_card(user, character) for user in users))

    assert results == [value, value]
    assert all(user.cred_token == "fresh-token" for user in users)
    assert get_card.await_count == 4
    assert refresh.await_count == 2


@pytest.mark.asyncio
async def test_box_handler_uses_shared_ark_card_data_source(app, mocker, monkeypatch):
    import nonebot_plugin_skland.commands.box as box

    user = mocker.Mock()
    character = mocker.Mock()
    match = mocker.Mock()
    session = mocker.Mock(commit=mocker.AsyncMock())
    user_session = mocker.Mock()
    monkeypatch.setattr(box, "gacha_table_data", mocker.Mock(operator_catalog=mocker.Mock(entries=(object(),))))
    mocker.patch.object(box, "_build_query", return_value=mocker.Mock())
    mocker.patch.object(box, "_resolve_target_id", new=mocker.AsyncMock(return_value=1))
    mocker.patch.object(box, "check_user_character", new=mocker.AsyncMock(return_value=(user, character)))
    mocker.patch.object(box, "send_reaction")
    get_card = mocker.patch.object(box, "get_ark_card", new=mocker.AsyncMock(return_value=None))

    await box.box_handler(
        session=session,
        user_session=user_session,
        target=match,
        filters=match,
        ownership=match,
        rarities=match,
        professions=match,
        branches=match,
        positions=match,
        genders=match,
        factions=match,
        races=match,
        potentials=match,
        name=match,
        sort=match,
        bot=mocker.Mock(),
    )

    get_card.assert_awaited_once_with(user, character)
    session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_card_handler_uses_shared_ark_card_data_source(app, mocker):
    import nonebot_plugin_skland.commands.card as card

    user = mocker.Mock()
    character = mocker.Mock()
    user_session = mocker.Mock(user_id=1)
    session = mocker.Mock(commit=mocker.AsyncMock())
    target = mocker.Mock(available=False)
    mocker.patch.object(card, "check_user_character", new=mocker.AsyncMock(return_value=(user, character)))
    mocker.patch.object(card, "send_reaction")
    get_card = mocker.patch.object(card, "get_ark_card", new=mocker.AsyncMock(return_value=None))

    await card.card_handler(session=session, user_session=user_session, target=target)

    get_card.assert_awaited_once_with(user, character)
    session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_gacha_handler_uses_shared_ark_card_data_source(app, mocker):
    import nonebot_plugin_skland.commands.gacha as gacha

    user = mocker.Mock(access_token="access-token")
    character = mocker.Mock(uid="role-1")
    user_session = mocker.Mock(user_id=1)
    session = mocker.Mock(commit=mocker.AsyncMock())
    target = mocker.Mock(available=False)
    mocker.patch.object(gacha, "check_user_character", new=mocker.AsyncMock(return_value=(user, character)))
    mocker.patch.object(gacha, "send_reaction")
    mocker.patch.object(gacha.SklandLoginAPI, "get_grant_code", new=mocker.AsyncMock(return_value="grant"))
    mocker.patch.object(gacha.SklandLoginAPI, "get_role_token_by_uid", new=mocker.AsyncMock(return_value="role"))
    mocker.patch.object(gacha.SklandLoginAPI, "get_ak_cookie", new=mocker.AsyncMock(return_value="cookie"))
    mocker.patch.object(gacha.SklandAPI, "get_gacha_categories", new=mocker.AsyncMock(return_value=[]))
    mocker.patch.object(gacha, "select_all_gacha_records", new=mocker.AsyncMock(return_value=[]))
    mocker.patch.object(gacha, "group_gacha_records", return_value=mocker.Mock())
    get_card = mocker.patch.object(gacha, "get_ark_card", new=mocker.AsyncMock(return_value=None))

    await gacha.gacha_handler(
        user_session=user_session,
        session=session,
        begin=mocker.Mock(available=False),
        limit=mocker.Mock(available=False),
        target=target,
        bot=mocker.Mock(),
    )

    get_card.assert_awaited_once_with(user, character)
    session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_bind_characters_invalidates_cached_player_data(app, mocker):
    from nonebot_plugin_skland.utils import bind_characters
    from nonebot_plugin_skland.player_data import ark_card_data

    user = mocker.Mock(id=7, cred="cred", cred_token="token")
    session = mocker.Mock()
    mocker.patch(
        "nonebot_plugin_skland.utils.SklandAPI.get_binding",
        new=mocker.AsyncMock(return_value=[]),
    )
    mocker.patch(
        "nonebot_plugin_skland.utils.select_user_characters",
        new=mocker.AsyncMock(return_value=[]),
    )
    invalidate = mocker.patch.object(ark_card_data, "invalidate_user", new=mocker.AsyncMock())

    await bind_characters(user, session)

    invalidate.assert_awaited_once_with(user.id)


@pytest.mark.asyncio
async def test_unbind_handler_invalidates_cached_player_data(app, mocker):
    import nonebot_plugin_skland.commands.bind as bind

    user = mocker.Mock(id=7)
    session = mocker.Mock(get=mocker.AsyncMock(return_value=user), commit=mocker.AsyncMock())
    response = mocker.Mock()
    response.extract_plain_text.return_value = "确认"
    mocker.patch.object(bind, "prompt", new=mocker.AsyncMock(return_value=response))
    mocker.patch.object(bind, "delete_user_all_gacha_records", new=mocker.AsyncMock())
    mocker.patch.object(bind, "delete_characters", new=mocker.AsyncMock())
    mocker.patch.object(bind, "delete_user", new=mocker.AsyncMock())
    mocker.patch.object(bind, "send_reaction")
    message = mocker.patch.object(bind, "UniMessage")
    message.return_value.finish = mocker.AsyncMock()
    invalidate = mocker.patch.object(bind.ark_card_data, "invalidate_user", new=mocker.AsyncMock())

    await bind.unbind_handler(user_session=mocker.Mock(user_id=7), session=session)

    session.commit.assert_awaited_once_with()
    invalidate.assert_awaited_once_with(user.id)
