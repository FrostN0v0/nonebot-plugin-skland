from types import SimpleNamespace

import pytest
from sqlalchemy import select, inspect


def _user_session(owner_id: int = 1, *, private: bool = True):
    return SimpleNamespace(
        user_id=owner_id,
        platform="QQClient",
        platform_user=SimpleNamespace(id=str(owner_id), avatar=None),
        session=SimpleNamespace(scene=SimpleNamespace(is_private=private)),
    )


def _snapshot(remote_id: str, role_id: str = "role-1"):
    from nonebot_plugin_skland.schemas import BindingRoleSnapshot, BindingAccountSnapshot

    return BindingAccountSnapshot(
        skland_user_id=remote_id,
        roles=[
            BindingRoleSnapshot(
                app_code="arknights",
                app_name="明日方舟",
                nickname="Doctor",
                binding_uid=role_id,
                game_role_id=role_id,
                server_id="1",
                server_name="Official",
                level=None,
                is_skland_default=True,
                is_available=True,
                unavailable_reason=None,
            )
        ],
    )


class _Reply:
    def __init__(self, text: str):
        self.text = text

    def extract_plain_text(self) -> str:
        return self.text


@pytest.mark.asyncio
async def test_binding_confirmation_projects_default_and_writes_after_confirm(app, mocker):
    from nonebot_plugin_orm import get_session

    import nonebot_plugin_skland.commands.bind as bind
    from nonebot_plugin_skland.model import SkUser, Character, CharacterDefault

    rendered_plans = []

    async with get_session() as session:

        async def render(card):
            assert session.in_transaction() is False
            rendered_plans.append(card)
            return b"card"

        async def confirm(*_args, **_kwargs):
            assert session.in_transaction() is False
            return _Reply("确认")

        mocker.patch.object(bind, "render_bound_roles_card", new=render)
        mocker.patch.object(bind, "prompt_until", new=confirm)
        mocker.patch.object(bind, "send_reaction")
        mocker.patch.object(bind.UniMessage, "send", new=mocker.AsyncMock(return_value=SimpleNamespace()))
        invalidate = mocker.patch.object(bind.ark_card_data, "invalidate_account", new=mocker.AsyncMock())

        await bind._confirm_account_binding(
            owner_id=1,
            pending=bind.PendingCredential(
                access_token="access",
                cred="cred",
                cred_token="token",
                skland_user_id="remote-1",
            ),
            snapshot=_snapshot("remote-1"),
            mode="add",
            user_session=_user_session(),
            session=session,
        )

        accounts = list(await session.scalars(select(SkUser)))
        characters = list(await session.scalars(select(Character)))
        defaults = list(await session.scalars(select(CharacterDefault)))
        assert len(accounts) == 1
        assert len(characters) == 1
        assert len(defaults) == 1
        assert defaults[0].character_id == characters[0].id
        assert rendered_plans[0].accounts[0].roles[0].is_local_default is True
        invalidate.assert_awaited_once_with(accounts[0].id)


@pytest.mark.asyncio
async def test_binding_cancel_and_empty_new_account_write_nothing(app, mocker):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.model import SkUser
    import nonebot_plugin_skland.commands.bind as bind
    from nonebot_plugin_skland.schemas import BindingAccountSnapshot

    mocker.patch.object(bind, "render_bound_roles_card", new=mocker.AsyncMock(return_value=b"card"))
    prompt = mocker.patch.object(bind, "prompt_until", new=mocker.AsyncMock(return_value=_Reply("取消")))
    mocker.patch.object(bind.UniMessage, "send", new=mocker.AsyncMock(return_value=SimpleNamespace()))

    async with get_session() as session:
        await bind._confirm_account_binding(
            owner_id=2,
            pending=bind.PendingCredential("access", "cred", "token", "remote-2"),
            snapshot=_snapshot("remote-2"),
            mode="add",
            user_session=_user_session(2),
            session=session,
        )
        assert list(await session.scalars(select(SkUser).where(SkUser.owner_id == 2))) == []

        prompt.reset_mock()
        await bind._confirm_account_binding(
            owner_id=3,
            pending=bind.PendingCredential("access", "cred", "token", "remote-3"),
            snapshot=BindingAccountSnapshot(skland_user_id="remote-3", roles=[]),
            mode="add",
            user_session=_user_session(3),
            session=session,
        )
        assert list(await session.scalars(select(SkUser).where(SkUser.owner_id == 3))) == []
        prompt.assert_not_awaited()


@pytest.mark.asyncio
async def test_cred_only_update_preserves_access_token(app, mocker):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.model import SkUser
    import nonebot_plugin_skland.commands.bind as bind
    from nonebot_plugin_skland.account import (
        apply_planned_defaults,
        build_bound_roles_plan,
        reconcile_account_characters,
    )

    mocker.patch.object(bind, "render_bound_roles_card", new=mocker.AsyncMock(return_value=b"card"))
    mocker.patch.object(bind, "prompt_until", new=mocker.AsyncMock(return_value=_Reply("确认")))
    mocker.patch.object(bind.UniMessage, "send", new=mocker.AsyncMock(return_value=SimpleNamespace()))
    mocker.patch.object(bind.ark_card_data, "invalidate_account", new=mocker.AsyncMock())

    async with get_session() as session:
        account = SkUser(
            owner_id=4,
            access_token="keep-access",
            cred="old-cred",
            cred_token="old-token",
            skland_user_id="remote-4",
        )
        session.add(account)
        await session.flush()
        account_id = account.id
        snapshot = _snapshot("remote-4")
        initial_plan = await build_bound_roles_plan(
            4,
            session,
            mode="overview",
            pending_snapshot=snapshot,
            pending_account_id=account_id,
        )
        await reconcile_account_characters(account, snapshot, session)
        await apply_planned_defaults(4, initial_plan.planned_defaults, session)
        await session.commit()

        await bind._confirm_account_binding(
            owner_id=4,
            pending=bind.PendingCredential(None, "new-cred", "new-token", "remote-4"),
            snapshot=snapshot,
            mode="update",
            user_session=_user_session(4),
            session=session,
        )
        refreshed = await session.get(SkUser, account_id)
        assert refreshed is not None
        assert refreshed.access_token == "keep-access"
        assert refreshed.cred == "new-cred"
        assert refreshed.cred_token == "new-token"


@pytest.mark.asyncio
async def test_binding_revalidates_state_after_waiter(app, mocker):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.model import SkUser
    import nonebot_plugin_skland.commands.bind as bind

    mocker.patch.object(bind, "render_bound_roles_card", new=mocker.AsyncMock(return_value=b"card"))
    mocker.patch.object(bind.UniMessage, "send", new=mocker.AsyncMock(return_value=SimpleNamespace()))

    async with get_session() as session:

        async def mutate_before_confirm(*_args, **_kwargs):
            assert session.in_transaction() is False
            session.add(
                SkUser(
                    owner_id=5,
                    access_token="other",
                    cred="other",
                    cred_token="other",
                    skland_user_id="concurrent",
                )
            )
            await session.commit()
            return _Reply("确认")

        mocker.patch.object(bind, "prompt_until", new=mutate_before_confirm)
        await bind._confirm_account_binding(
            owner_id=5,
            pending=bind.PendingCredential("access", "cred", "token", "remote-5"),
            snapshot=_snapshot("remote-5"),
            mode="add",
            user_session=_user_session(5),
            session=session,
        )

        accounts = list(await session.scalars(select(SkUser).where(SkUser.owner_id == 5)))
        assert [account.skland_user_id for account in accounts] == ["concurrent"]


@pytest.mark.asyncio
async def test_manual_bind_fetches_binding_once_and_delegates_confirmation(app, mocker):
    import nonebot_plugin_skland.commands.bind as bind

    pending = bind.PendingCredential("access", "cred", "token", "remote")
    mocker.patch.object(bind, "_resolve_pending_credential", new=mocker.AsyncMock(return_value=pending))
    get_binding = mocker.patch.object(bind.SklandAPI, "get_binding", new=mocker.AsyncMock(return_value=[]))
    confirm = mocker.patch.object(bind, "_confirm_account_binding", new=mocker.AsyncMock())

    await bind.bind_handler(
        token=SimpleNamespace(available=True, result="x"),
        result=SimpleNamespace(find=lambda _path: False),
        user_session=_user_session(6),
        msg_target=SimpleNamespace(private=True),
        session=SimpleNamespace(),
    )

    get_binding.assert_awaited_once()
    confirm.assert_awaited_once()
    assert confirm.await_args.kwargs["mode"] == "add"


@pytest.mark.parametrize(
    ("selection", "remaining_remote_ids"),
    [("1", ["remote-b"]), ("\u5168\u90e8", [])],
)
@pytest.mark.asyncio
async def test_unbind_waiters_run_without_transactions_and_delete_selected_account(
    app, mocker, make_user_session, selection, remaining_remote_ids
):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.model import SkUser
    import nonebot_plugin_skland.commands.bind as bind

    async with get_session() as session:
        first = SkUser(
            owner_id=7,
            access_token="a",
            cred="a",
            cred_token="a",
            skland_user_id="remote-a",
        )
        second = SkUser(
            owner_id=7,
            access_token="b",
            cred="b",
            cred_token="b",
            skland_user_id="remote-b",
        )
        session.add_all([first, second])
        await session.flush()
        first_id = first.id
        second_id = second.id
        await session.commit()
        user_session = await make_user_session(session, 7)
        rendered_modes = []

        async def render(card):
            assert session.in_transaction() is False
            assert inspect(user_session.user).expired
            rendered_modes.append(card.mode)
            return b"card"

        replies = iter([_Reply(selection), _Reply("\u786e\u8ba4")])

        async def prompt(*_args, **_kwargs):
            assert session.in_transaction() is False
            assert inspect(user_session.user).expired
            return next(replies)

        mocker.patch.object(bind, "render_bound_roles_card", new=render)
        waiter = mocker.patch.object(bind, "prompt_until", new=mocker.AsyncMock(side_effect=prompt))
        mocker.patch.object(bind, "send_reaction")
        mocker.patch.object(bind.UniMessage, "send", new=mocker.AsyncMock(return_value=SimpleNamespace()))
        invalidate = mocker.patch.object(bind.ark_card_data, "invalidate_account", new=mocker.AsyncMock())

        await bind.unbind_handler(user_session, session)

        assert session.in_transaction() is False
        assert inspect(user_session.user).expired
        assert rendered_modes == ["unbind_selection", "unbind_confirmation"] + (
            ["overview"] if remaining_remote_ids else []
        )

        remaining = list(await session.scalars(select(SkUser).where(SkUser.owner_id == 7)))
        assert [account.skland_user_id for account in remaining] == remaining_remote_ids
        assert waiter.call_count == 2
        expected_invalidations = [mocker.call(first_id)]
        if not remaining_remote_ids:
            expected_invalidations.append(mocker.call(second_id))
        invalidate.assert_has_awaits(expected_invalidations, any_order=True)
        assert invalidate.await_count == len(expected_invalidations)
