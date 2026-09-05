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
            expected = (
                "\u76ee\u6807\u7528\u6237\u5c1a\u672a\u8bbe\u7f6e"
                if feedback == "target_missing"
                else "\u4f60\u8fd8\u6ca1\u6709\u7ed1\u5b9a"
            )
            assert messages[0].startswith(expected)
