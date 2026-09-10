"""Behavior tests for short-lived ArkCard caching."""

import asyncio
from typing import Any
from types import SimpleNamespace

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
    user = mocker.Mock(id=1, skland_user_id="account-1")
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
    user = mocker.Mock(id=1, skland_user_id="account-1")
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
    user = mocker.Mock(id=1, skland_user_id="account-1")
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
    user = mocker.Mock(id=1, skland_user_id="account-1")
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
    user = mocker.Mock(id=1, skland_user_id="account-1")
    character = mocker.Mock(
        app_code="arknights",
        channel_master_id="server-1",
        uid="role-1",
        role_id="role-id-1",
    )

    first = await source.get(user, character)
    await source.invalidate_account(user.id)
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
    user = mocker.Mock(id=1, skland_user_id="account-1")
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
    user = mocker.Mock(id=1, skland_user_id="account-1")

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
    user = mocker.Mock(id=1, skland_user_id="account-1")

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
    user = mocker.Mock(id=1, skland_user_id="account-1")
    character = mocker.Mock(
        app_code="arknights",
        channel_master_id="server-1",
        uid="role-1",
        role_id="role-id-1",
    )

    first_request = asyncio.create_task(source.get(user, character))
    await started.wait()
    await source.invalidate_account(user.id)
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
        skland_user_id="account-99",
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
    await ark_card_data.invalidate_account(user.id)

    result = await get_ark_card(user, character)

    assert result is value
    cred, uid = fetch.await_args.args
    assert cred.cred == "cred-value"
    assert cred.token == "cred-token-value"
    assert uid == "role-99"
    await ark_card_data.invalidate_account(user.id)


@pytest.mark.asyncio
async def test_get_ark_card_refreshes_each_waiter_context(app, mocker):
    from nonebot_plugin_skland.api import SklandLoginAPI
    import nonebot_plugin_skland.player_data as player_data
    from nonebot_plugin_skland.exception import UnauthorizedException

    value = object()
    loads = []
    both_refreshed = asyncio.Event()
    refreshes = 0

    async def load(user, _character):
        loads.append(user.cred_token)
        if user.cred_token == "expired-token":
            raise UnauthorizedException("expired")
        return value

    async def refresh(_cred):
        nonlocal refreshes
        refreshes += 1
        if refreshes == 2:
            both_refreshed.set()
        await asyncio.wait_for(both_refreshed.wait(), timeout=1)
        return "fresh-token"

    source = player_data.ArkCardDataSource(ttl=60, max_entries=10, loader=load)
    mocker.patch.object(player_data, "ark_card_data", source)
    mocker.patch.object(SklandLoginAPI, "refresh_token", new=refresh)
    users = [
        SimpleNamespace(id=1, skland_user_id="remote", cred="cred-value", cred_token="expired-token") for _ in range(2)
    ]
    character = SimpleNamespace(app_code="arknights", channel_master_id="1", uid="uid", role_id="role")

    results = await asyncio.gather(*(player_data.get_ark_card(user, character) for user in users))

    assert results == [value, value]
    assert all(user.cred_token == "fresh-token" for user in users)
    assert loads == ["expired-token", "fresh-token"]
    assert refreshes == 2


@pytest.mark.asyncio
async def test_gacha_handler_renders_after_session_commit(app, mocker, tiny_png):
    from nonebot_plugin_orm import get_session

    import nonebot_plugin_skland.render as render
    import nonebot_plugin_skland.commands.gacha as gacha
    from nonebot_plugin_skland.compact import template_to_html
    from nonebot_plugin_skland.model import SkUser, Character, CharacterDefault

    rendered_html: list[str] = []

    async def render_template(**kwargs) -> bytes:
        html = await template_to_html(
            template_path=kwargs["template_path"],
            template_name=kwargs["template_name"],
            filters=kwargs["filters"],
            **kwargs["templates"],
        )
        rendered_html.append(html)
        return tiny_png

    mocker.patch.object(render, "template_to_pic", new=render_template)
    mocker.patch.object(gacha, "send_reaction")
    mocker.patch.object(gacha.SklandLoginAPI, "get_grant_code", new=mocker.AsyncMock(return_value="grant"))
    mocker.patch.object(gacha.SklandLoginAPI, "get_role_token_by_uid", new=mocker.AsyncMock(return_value="role"))
    mocker.patch.object(gacha.SklandLoginAPI, "get_ak_cookie", new=mocker.AsyncMock(return_value="cookie"))
    mocker.patch.object(gacha.SklandAPI, "get_gacha_categories", new=mocker.AsyncMock(return_value=[]))
    mocker.patch.object(
        gacha,
        "get_ark_card",
        new=mocker.AsyncMock(
            return_value=SimpleNamespace(
                status=SimpleNamespace(avatar=SimpleNamespace(url="avatar"), level=120),
            )
        ),
    )
    message = SimpleNamespace(send=mocker.AsyncMock())
    mocker.patch.object(gacha.UniMessage, "image", return_value=message)

    async with get_session() as session:
        owner_id = 91001
        user = SkUser(
            owner_id=owner_id,
            access_token="access-token",
            cred="cred",
            cred_token="cred-token",
            skland_user_id="skland-user",
        )
        session.add(user)
        await session.flush()
        character = Character(
            account_id=user.id,
            uid="role-1",
            role_id="role-1",
            app_code="arknights",
            channel_master_id="1",
            server_name="Official",
            nickname="Doctor",
            level=None,
            is_skland_default=True,
        )
        session.add(character)
        await session.flush()
        session.add(CharacterDefault(owner_id=owner_id, app_code="arknights", character_id=character.id))
        await session.commit()

        await gacha.gacha_handler(
            user_session=SimpleNamespace(user_id=owner_id),
            session=session,
            begin=mocker.Mock(available=False),
            limit=mocker.Mock(available=False),
            target=mocker.Mock(available=False),
            bot=SimpleNamespace(self_id="bot"),
        )

    assert len(rendered_html) == 1
    assert "Doctor" in rendered_html[0]
    message.send.assert_awaited_once_with()
