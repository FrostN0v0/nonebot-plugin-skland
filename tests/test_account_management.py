import asyncio

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError


async def _make_account(session, *, owner_id: int, remote_id: str, suffix: str):
    from nonebot_plugin_skland.model import SkUser

    account = SkUser(
        owner_id=owner_id,
        access_token=f"access-{suffix}",
        cred=f"cred-{suffix}",
        cred_token=f"token-{suffix}",
        skland_user_id=remote_id,
    )
    session.add(account)
    await session.flush()
    return account


async def _make_character(
    session,
    *,
    account_id: int,
    app_code: str,
    binding_uid: str,
    role_id: str,
    server_id: str,
    nickname: str,
):
    from nonebot_plugin_skland.model import Character

    character = Character(
        account_id=account_id,
        uid=binding_uid,
        role_id=role_id,
        app_code=app_code,
        channel_master_id=server_id,
        server_name=f"Server {server_id}",
        nickname=nickname,
        level=10 if app_code == "endfield" else None,
        is_skland_default=False,
    )
    session.add(character)
    await session.flush()
    return character


async def _seed_role_selection_data(session, *, owner_id: int):
    accounts = [
        await _make_account(
            session,
            owner_id=owner_id,
            remote_id=f"remote-{owner_id}-first",
            suffix=f"{owner_id}-first",
        ),
        await _make_account(
            session,
            owner_id=owner_id,
            remote_id=f"remote-{owner_id}-second",
            suffix=f"{owner_id}-second",
        ),
    ]
    roles = {}
    for app_code in ("arknights", "endfield"):
        roles[app_code] = (
            await _make_character(
                session,
                account_id=accounts[0].id,
                app_code=app_code,
                binding_uid=f"{app_code}-first-binding",
                role_id=f"{app_code}-first",
                server_id="1",
                nickname=f"{app_code} first",
            ),
            await _make_character(
                session,
                account_id=accounts[1].id,
                app_code=app_code,
                binding_uid=f"{app_code}-second-binding",
                role_id=f"{app_code}-second",
                server_id="2",
                nickname=f"{app_code} second",
            ),
        )
    return accounts[0], accounts[1], roles


@pytest.mark.asyncio
async def test_multi_account_defaults_and_gacha_are_role_scoped(app):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.model import GachaRecord
    from nonebot_plugin_skland.db_handler import (
        get_default_character,
        set_default_character,
        get_character_gacha_records,
    )

    async with get_session() as session:
        first = await _make_account(session, owner_id=1, remote_id="remote-a", suffix="a")
        second = await _make_account(session, owner_id=1, remote_id="remote-b", suffix="b")
        ark = await _make_character(
            session,
            account_id=first.id,
            app_code="arknights",
            binding_uid="ark-binding",
            role_id="ark-role",
            server_id="1",
            nickname="Doctor",
        )
        ef_first = await _make_character(
            session,
            account_id=second.id,
            app_code="endfield",
            binding_uid="ef-binding",
            role_id="ef-role-a",
            server_id="1",
            nickname="Admin",
        )
        ef_second = await _make_character(
            session,
            account_id=second.id,
            app_code="endfield",
            binding_uid="ef-binding",
            role_id="ef-role-b",
            server_id="2",
            nickname="Admin",
        )
        await set_default_character(1, "arknights", ark.id, session)
        await set_default_character(1, "endfield", ef_second.id, session)
        ef_first_id = ef_first.id
        ef_second_id = ef_second.id
        for character in (ef_first, ef_second):
            session.add(
                GachaRecord(
                    character_id=character.id,
                    pool_id="pool",
                    pool_name="Pool",
                    item_type="char",
                    char_id="item",
                    char_name="Item",
                    rarity=6,
                    is_new=False,
                    is_free=False,
                    gacha_ts=100,
                    pos=1,
                )
            )
        await session.commit()

        ark_default = await get_default_character(1, "arknights", session)
        ef_default = await get_default_character(1, "endfield", session)
        assert ark_default is not None
        assert ark_default.account.access_token == "access-a"
        assert ef_default is not None
        assert ef_default.role_id == "ef-role-b"
        assert len(await get_character_gacha_records(ef_first_id, session)) == 1
        assert len(await get_character_gacha_records(ef_second_id, session)) == 1


@pytest.mark.asyncio
async def test_account_identity_unique_per_owner_only(app):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.model import SkUser

    async with get_session() as session:
        await _make_account(session, owner_id=10, remote_id="shared", suffix="one")
        await _make_account(session, owner_id=11, remote_id="shared", suffix="two")
        await session.commit()

        session.add(
            SkUser(
                owner_id=10,
                access_token="duplicate",
                cred="duplicate",
                cred_token="duplicate",
                skland_user_id="shared",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_default_setter_rejects_cross_owner_and_cross_game(app):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.db_handler import get_default_character, set_default_character

    async with get_session() as session:
        account = await _make_account(session, owner_id=20, remote_id="remote", suffix="owner")
        character = await _make_character(
            session,
            account_id=account.id,
            app_code="arknights",
            binding_uid="ark",
            role_id="ark",
            server_id="1",
            nickname="Doctor",
        )
        with pytest.raises(ValueError, match="does not belong"):
            await set_default_character(21, "arknights", character.id, session)
        with pytest.raises(ValueError, match="does not belong"):
            await set_default_character(20, "endfield", character.id, session)
        assert await get_default_character(20, "arknights", session) is None


@pytest.mark.asyncio
async def test_reconcile_clears_removed_default_without_replacement(app):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.model import SkUser
    from nonebot_plugin_skland.schemas import BindingRoleSnapshot, BindingAccountSnapshot
    from nonebot_plugin_skland.db_handler import get_user_characters, get_default_character, set_default_character
    from nonebot_plugin_skland.account import (
        apply_planned_defaults,
        build_bound_roles_plan,
        reconcile_account_characters,
    )

    async with get_session() as session:
        account = await _make_account(session, owner_id=30, remote_id="remote", suffix="owner")
        old = await _make_character(
            session,
            account_id=account.id,
            app_code="arknights",
            binding_uid="old",
            role_id="old",
            server_id="1",
            nickname="Old",
        )
        await set_default_character(30, "arknights", old.id, session)
        account_id = account.id
        await session.commit()
        account = await session.get(SkUser, account_id)
        assert account is not None

        snapshot = BindingAccountSnapshot(
            skland_user_id="remote",
            roles=[
                BindingRoleSnapshot(
                    app_code="arknights",
                    app_name="明日方舟",
                    nickname="New",
                    binding_uid="new",
                    game_role_id="new",
                    server_id="2",
                    server_name="Server 2",
                    level=None,
                    is_skland_default=True,
                    is_available=True,
                    unavailable_reason=None,
                )
            ],
        )
        plan = await build_bound_roles_plan(
            30,
            session,
            mode="overview",
            pending_snapshot=snapshot,
            pending_account_id=account_id,
        )
        removed = await reconcile_account_characters(account, snapshot, session)
        await apply_planned_defaults(30, plan.planned_defaults, session)
        await session.commit()

        assert removed == {"arknights"}
        assert [character.role_id for character in await get_user_characters(30, "arknights", session)] == ["new"]
        assert await get_default_character(30, "arknights", session) is None


@pytest.mark.asyncio
async def test_account_operation_lock_rejects_same_owner_only(app):
    from nonebot_plugin_skland.account import AccountOperationInProgress, exclusive_account_operation

    entered = asyncio.Event()
    release = asyncio.Event()

    async def hold() -> None:
        async with exclusive_account_operation(40):
            entered.set()
            await release.wait()

    task = asyncio.create_task(hold())
    await entered.wait()
    with pytest.raises(AccountOperationInProgress):
        async with exclusive_account_operation(40):
            pass
    async with exclusive_account_operation(41):
        pass
    release.set()
    await task
    async with exclusive_account_operation(40):
        pass


@pytest.mark.asyncio
async def test_account_sync_commits_success_before_later_failure(app, mocker):
    from nonebot_plugin_orm import get_session

    import nonebot_plugin_skland.commands.char as char_command
    from nonebot_plugin_skland.db_handler import get_user_characters
    from nonebot_plugin_skland.schemas import BindingRoleSnapshot, BindingAccountSnapshot

    async with get_session() as session:
        first = await _make_account(session, owner_id=50, remote_id="remote-a", suffix="a")
        second = await _make_account(session, owner_id=50, remote_id="remote-b", suffix="b")
        first_id = first.id
        second_id = second.id
        await session.commit()

        snapshot = BindingAccountSnapshot(
            skland_user_id="remote-a",
            roles=[
                BindingRoleSnapshot(
                    app_code="arknights",
                    app_name="明日方舟",
                    nickname="Doctor",
                    binding_uid="role-a",
                    game_role_id="role-a",
                    server_id="1",
                    server_name="Official",
                    level=None,
                    is_skland_default=True,
                    is_available=True,
                    unavailable_reason=None,
                )
            ],
        )
        mocker.patch.object(
            char_command,
            "_fetch_account_snapshot",
            new=mocker.AsyncMock(side_effect=[snapshot, "request failed"]),
        )
        mocker.patch.object(char_command.ark_card_data, "invalidate_account", new=mocker.AsyncMock())

        first_result = await char_command._sync_account(first_id, session)
        second_result = await char_command._sync_account(second_id, session)

        assert first_result.success is True
        assert second_result.success is False
        assert [character.role_id for character in await get_user_characters(50, "arknights", session)] == ["role-a"]


@pytest.mark.asyncio
async def test_unsupported_persisted_roles_are_hidden_and_preserved(app):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.model import Character, CharacterDefault
    from nonebot_plugin_skland.schemas import BindingRoleSnapshot, BindingAccountSnapshot
    from nonebot_plugin_skland.account import build_bound_roles_plan, reconcile_account_characters

    async with get_session() as session:
        account = await _make_account(session, owner_id=60, remote_id="remote", suffix="owner")
        await _make_character(
            session,
            account_id=account.id,
            app_code="arknights",
            binding_uid="ark",
            role_id="ark",
            server_id="1",
            nickname="Doctor",
        )
        unsupported = await _make_character(
            session,
            account_id=account.id,
            app_code="exa",
            binding_uid="exa",
            role_id="exa",
            server_id="2",
            nickname="Traveler",
        )
        session.add(CharacterDefault(owner_id=60, app_code="exa", character_id=unsupported.id))
        unsupported_id = unsupported.id
        await session.commit()

        plan = await build_bound_roles_plan(60, session, mode="overview")

        assert [role.app_code for item in plan.card.accounts for role in item.roles] == ["arknights"]

        snapshot = BindingAccountSnapshot(
            skland_user_id="remote",
            roles=[
                BindingRoleSnapshot(
                    app_code="arknights",
                    app_name="Arknights",
                    nickname="Doctor",
                    binding_uid="ark",
                    game_role_id="ark",
                    server_id="1",
                    server_name="Server 1",
                    level=None,
                    is_skland_default=False,
                    is_available=True,
                    unavailable_reason=None,
                )
            ],
        )
        await reconcile_account_characters(account, snapshot, session)
        await session.flush()

        assert await session.get(Character, unsupported_id) is not None
        assert await session.get(CharacterDefault, (60, "exa")) is not None


@pytest.mark.parametrize(
    ("module_name", "game_token"),
    [("nonebot_plugin_skland.commands.card", "ark"), ("nonebot_plugin_skland.commands.endfield.utils", "ef")],
)
@pytest.mark.parametrize("feedback", ["own_missing", "target_missing", "own_unbound"])
@pytest.mark.asyncio
async def test_missing_default_feedback_survives_expired_user_session(
    app, mocker, make_user_session, module_name, game_token, feedback
):
    from importlib import import_module

    from nonebot_plugin_orm import get_session

    import nonebot_plugin_skland.commands.char as char_command

    command = import_module(module_name)
    target_owner_id = 81 if feedback == "target_missing" else 80
    async with get_session() as session:
        if feedback != "own_unbound":
            await _make_account(session, owner_id=target_owner_id, remote_id="remote", suffix="target")
        user_session = await make_user_session(session, 80)
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
            messages.append(message.extract_plain_text())

        mocker.patch.object(char_command, "render_bound_roles_card", new=render)
        mocker.patch.object(command.UniMessage, "send", new=send)
        selected = await command.check_user_character(target_owner_id, user_session, session)

        assert selected is None
        assert session.in_transaction() is False
        assert len(messages) == 1
        if feedback == "own_missing":
            assert len(rendered_cards) == 1
            assert f"sk char set {game_token}" in messages[0]
        else:
            assert rendered_cards == []
            expected = "目标用户尚未设置" if feedback == "target_missing" else "你还没有绑定"
            assert messages[0].startswith(expected)


@pytest.mark.parametrize(
    ("module_name", "app_code"),
    [
        ("nonebot_plugin_skland.commands.card", "arknights"),
        ("nonebot_plugin_skland.commands.endfield.utils", "endfield"),
    ],
)
@pytest.mark.asyncio
async def test_explicit_role_selection_uses_overview_index_without_changing_defaults(
    app, make_user_session, module_name, app_code
):
    from importlib import import_module

    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.account import build_bound_roles_plan
    from nonebot_plugin_skland.db_handler import get_default_character, set_default_character

    async with get_session() as session:
        _first_account, second_account, roles = await _seed_role_selection_data(session, owner_id=100)
        for game_roles in roles.values():
            await set_default_character(100, game_roles[0].app_code, game_roles[0].id, session)
        await session.commit()

        plan = await build_bound_roles_plan(100, session, mode="overview")
        indexed_roles = [
            role
            for account_card in plan.card.accounts
            for role in account_card.roles
            if role.app_code == app_code and role.is_available
        ]
        assert [role.index for role in indexed_roles] == [1, 2]
        target_character = roles[app_code][1]
        role_index = next(role.index for role in indexed_roles if role.game_role_id == target_character.role_id)
        assert role_index == 2

        command = import_module(module_name)
        user_session = await make_user_session(session, 100)
        selected = await command.check_user_character(100, user_session, session, role_index=role_index)

        assert selected is not None
        assert selected[0].id == second_account.id
        assert selected[1].id == target_character.id
        assert (await get_default_character(100, "arknights", session)).id == roles["arknights"][0].id
        assert (await get_default_character(100, "endfield", session)).id == roles["endfield"][0].id


@pytest.mark.parametrize(
    ("module_name", "app_code"),
    [
        ("nonebot_plugin_skland.commands.card", "arknights"),
        ("nonebot_plugin_skland.commands.endfield.utils", "endfield"),
    ],
)
@pytest.mark.asyncio
async def test_explicit_role_selection_does_not_require_default(app, make_user_session, module_name, app_code):
    from importlib import import_module

    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.db_handler import get_default_character

    async with get_session() as session:
        _first_account, second_account, roles = await _seed_role_selection_data(session, owner_id=110)
        await session.commit()

        command = import_module(module_name)
        user_session = await make_user_session(session, 110)
        selected = await command.check_user_character(110, user_session, session, role_index=2)

        assert selected is not None
        assert selected[0].id == second_account.id
        assert selected[1].id == roles[app_code][1].id
        assert await get_default_character(110, app_code, session) is None


@pytest.mark.parametrize(
    ("module_name", "app_code"),
    [
        ("nonebot_plugin_skland.commands.card", "arknights"),
        ("nonebot_plugin_skland.commands.endfield.utils", "endfield"),
    ],
)
@pytest.mark.parametrize("role_index", [0, 3])
@pytest.mark.asyncio
async def test_explicit_role_selection_rejects_boundary_without_default_fallback(
    app, mocker, make_user_session, module_name, app_code, role_index
):
    from importlib import import_module

    from nonebot_plugin_orm import get_session

    import nonebot_plugin_skland.commands.char as char_command
    from nonebot_plugin_skland.db_handler import get_default_character, set_default_character

    async with get_session() as session:
        _first_account, _second_account, roles = await _seed_role_selection_data(session, owner_id=120)
        default_character_id = roles[app_code][0].id
        await set_default_character(120, app_code, default_character_id, session)
        await session.commit()
        user_session = await make_user_session(session, 120)
        command = import_module(module_name)
        rendered_cards = []
        messages = []

        async def render(card):
            rendered_cards.append(card)
            return b"card"

        async def send(message, **_kwargs):
            messages.append(message.extract_plain_text())

        mocker.patch.object(char_command, "render_bound_roles_card", new=render)
        mocker.patch.object(command.UniMessage, "send", new=send)

        selected = await command.check_user_character(120, user_session, session, role_index=role_index)

        assert selected is None
        assert len(rendered_cards) == 1
        assert len(messages) == 1
        assert (await get_default_character(120, app_code, session)).id == default_character_id


@pytest.mark.parametrize(
    ("module_name", "app_code"),
    [
        ("nonebot_plugin_skland.commands.card", "arknights"),
        ("nonebot_plugin_skland.commands.endfield.utils", "endfield"),
    ],
)
@pytest.mark.asyncio
async def test_explicit_role_selection_rejects_other_owner_before_lookup(
    app, mocker, make_user_session, module_name, app_code
):
    from importlib import import_module

    from nonebot_plugin_orm import get_session

    async with get_session() as session:
        await _seed_role_selection_data(session, owner_id=130)
        await session.commit()
        user_session = await make_user_session(session, 131)
        command = import_module(module_name)
        lookup = mocker.patch.object(command, "get_character_by_index", new=mocker.AsyncMock())
        overview = mocker.patch.object(command, "send_bound_roles_overview", new=mocker.AsyncMock())
        messages = []

        async def send(message, **_kwargs):
            messages.append(message.extract_plain_text())

        mocker.patch.object(command.UniMessage, "send", new=send)

        selected = await command.check_user_character(130, user_session, session, role_index=1)

        assert selected is None
        lookup.assert_not_awaited()
        overview.assert_not_awaited()
        assert len(messages) == 1


@pytest.mark.parametrize("game", ["arknights", "endfield"])
@pytest.mark.asyncio
async def test_card_handler_uses_requested_role_data_path(app, mocker, make_user_session, game):
    from nonebot_plugin_alconna import Match
    from nonebot_plugin_orm import get_session

    import nonebot_plugin_skland.commands.card as ark_card
    import nonebot_plugin_skland.commands.endfield.card as ef_card
    from nonebot_plugin_skland.db_handler import set_default_character

    async with get_session() as session:
        _first_account, second_account, roles = await _seed_role_selection_data(session, owner_id=140)
        first_character, second_character = roles[game]
        second_account_id = second_account.id
        second_remote_id = second_account.skland_user_id
        second_character_id = second_character.id
        await set_default_character(140, game, first_character.id, session)
        await session.commit()
        user_session = await make_user_session(session, 140)

        if game == "arknights":
            calls = []

            async def get_card(user, character):
                calls.append((user.id, user.skland_user_id, character.id))
                return None

            mocker.patch.object(ark_card, "get_ark_card", new=get_card)
            mocker.patch.object(ark_card, "send_reaction")
            await ark_card.card_handler(
                session,
                user_session,
                Match(0, available=False),
                role_index=2,
            )

            assert calls == [(second_account_id, second_remote_id, second_character_id)]
        else:
            calls = []

            async def get_card(_cred, remote_id, character):
                calls.append((remote_id, character.id))
                return None

            mocker.patch.object(ef_card.SklandAPI, "endfield_card", new=get_card)
            mocker.patch.object(ef_card, "send_reaction")
            await ef_card.efcard_handler(
                user_session,
                session,
                Match(0, available=False),
                role_index=2,
            )

            assert calls == [(second_remote_id, second_character_id)]
