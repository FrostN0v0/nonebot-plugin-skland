import re
from pathlib import Path
from html.parser import HTMLParser

import pytest
from nonebot.compat import model_dump
from jinja2 import Environment, FileSystemLoader


class _VisibleTextParser(HTMLParser):
    _ignored_tags = frozenset({"head", "script", "style", "title"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._ignored_tags:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def _visible_text(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    parser.close()
    return " ".join("".join(parser.parts).split())


def _contains_visible_token(text: str, token: str) -> bool:
    return re.search(rf"(?<![0-9A-Za-z_]){re.escape(token)}(?![0-9A-Za-z_])", text) is not None


def _bound_roles_template():
    template_dir = Path("nonebot_plugin_skland/resources/templates")
    environment = Environment(loader=FileSystemLoader(template_dir))
    return environment.get_template("bound_roles.html.jinja2")


def _binding_apps():
    from nonebot_plugin_skland.schemas import Role, BindingApp, BindingCharacter

    long_uid = "ark-123456789012345678901234567890"
    return [
        BindingApp(
            appCode="arknights",
            appName="Ignored Ark Name",
            defaultUid=long_uid,
            bindingList=[
                BindingCharacter(
                    uid=long_uid,
                    isOfficial=True,
                    isDefault=False,
                    channelMasterId="1001",
                    channelName="官服",
                    nickName="Doctor <Main>",
                    isDelete=False,
                    gameName="Arknights",
                    gameId=1,
                    roles=[],
                    defaultRole=None,
                ),
                BindingCharacter(
                    uid="deleted-role",
                    isOfficial=True,
                    isDefault=False,
                    channelMasterId="1002",
                    channelName="B服",
                    nickName="Deleted",
                    isDelete=True,
                    gameName="Arknights",
                    gameId=1,
                    roles=[],
                    defaultRole=None,
                ),
            ],
        ),
        BindingApp(
            appCode="endfield",
            appName="Ignored Endfield Name",
            defaultUid="endfield-parent",
            bindingList=[
                BindingCharacter(
                    uid="endfield-parent",
                    isOfficial=True,
                    isDefault=False,
                    channelMasterId="",
                    channelName="",
                    nickName="",
                    isDelete=False,
                    gameName="Endfield",
                    gameId=2,
                    roles=[
                        Role(
                            serverId="2001",
                            roleId="ef-role-a",
                            nickname="Admin",
                            level=20,
                            isDefault=True,
                            isBanned=False,
                            serverType="official",
                            serverName="China",
                        ),
                        Role(
                            serverId="2002",
                            roleId="ef-role-b",
                            nickname="Admin",
                            level=10,
                            isDefault=False,
                            isBanned=True,
                            serverType="official",
                            serverName="哨站乙",
                        ),
                    ],
                    defaultRole=None,
                )
            ],
        ),
    ]


def test_binding_snapshot_normalizes_games_and_unavailable_roles(app):
    from nonebot_plugin_skland.schemas import BindingAccountSnapshot

    snapshot = BindingAccountSnapshot.from_apps("remote-account-two-long", _binding_apps())

    assert [role.app_code for role in snapshot.roles] == [
        "arknights",
        "arknights",
        "endfield",
        "endfield",
    ]
    assert snapshot.roles[0].app_name == "明日方舟"
    assert snapshot.roles[0].game_role_id == snapshot.roles[0].binding_uid
    assert snapshot.roles[0].is_skland_default is True
    assert snapshot.roles[1].is_available is False
    assert snapshot.roles[1].unavailable_reason == "角色已删除"
    assert snapshot.roles[2].app_name == "明日方舟：终末地"
    assert snapshot.roles[2].game_role_id == "ef-role-a"
    assert snapshot.roles[3].is_available is False
    assert snapshot.roles[3].unavailable_reason == "角色已封禁"


def test_bound_role_card_item_player_uid_uses_public_identifier_per_game(app):
    from nonebot_plugin_skland.schemas import BoundRoleCardItem

    common = {
        "app_name": "展示名称",
        "nickname": "展示角色",
        "server_id": "internal-server-code",
        "server_name": "可见服务器",
        "level": None,
        "is_skland_default": False,
        "is_available": True,
        "unavailable_reason": None,
        "index": 1,
        "is_local_default": False,
    }
    arknights = BoundRoleCardItem(
        app_code="arknights",
        binding_uid="ark-player-uid",
        game_role_id="ark-internal-role-id",
        **common,
    )
    endfield = BoundRoleCardItem(
        app_code="endfield",
        binding_uid="endfield-binding-parent",
        game_role_id="endfield-player-uid",
        **common,
    )

    assert arknights.binding_uid != arknights.game_role_id
    assert endfield.binding_uid != endfield.game_role_id
    assert arknights.player_uid == "ark-player-uid"
    assert endfield.player_uid == "endfield-player-uid"


@pytest.mark.parametrize(
    ("app_code", "server_name", "expected"),
    [("endfield", "China", "\u56fd\u670d"), ("endfield", "Asia", "Asia"), ("arknights", "China", "China")],
)
def test_bound_role_server_label_preserves_raw_identity(app, app_code, server_name, expected):
    from nonebot_plugin_skland.schemas import BoundRoleCardItem

    role = BoundRoleCardItem(
        app_code=app_code,
        app_name="Game",
        nickname="Player",
        binding_uid="binding-uid",
        game_role_id="player-uid",
        server_id="server-code",
        server_name=server_name,
        level=None,
        is_skland_default=False,
        is_available=True,
        unavailable_reason=None,
        index=1,
        is_local_default=False,
    )

    assert role.server_label == expected
    assert role.server_name == server_name
    assert role.server_id == "server-code"


@pytest.mark.asyncio
async def test_bound_roles_plan_numbers_each_game_and_projects_defaults(app):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.model import SkUser, Character
    from nonebot_plugin_skland.account import build_bound_roles_plan
    from nonebot_plugin_skland.schemas import BindingAccountSnapshot
    from nonebot_plugin_skland.db_handler import set_default_character

    async with get_session() as session:
        existing = SkUser(
            owner_id=100,
            access_token="access",
            cred="cred",
            cred_token="token",
            skland_user_id="remote-account-one",
        )
        session.add(existing)
        await session.flush()
        existing_role = Character(
            account_id=existing.id,
            uid="existing-ark",
            role_id="existing-ark",
            app_code="arknights",
            channel_master_id="0",
            server_name="Existing",
            nickname="Doctor <Main>",
            level=None,
            is_skland_default=False,
        )
        session.add(existing_role)
        await session.flush()
        await set_default_character(100, "arknights", existing_role.id, session)
        await session.commit()

        pending = BindingAccountSnapshot.from_apps("remote-account-two-long", _binding_apps())
        plan = await build_bound_roles_plan(
            100,
            session,
            mode="bind_confirmation",
            pending_snapshot=pending,
        )

        assert [account.account_hint for account in plan.card.accounts] == ["••••-one", "••••long"]
        assert [account.state for account in plan.card.accounts] == ["bound", "pending_bind"]
        ark_roles = [role for account in plan.card.accounts for role in account.roles if role.app_code == "arknights"]
        ef_roles = [role for account in plan.card.accounts for role in account.roles if role.app_code == "endfield"]
        assert [role.index for role in ark_roles] == [1, 2, None]
        assert [role.index for role in ef_roles] == [1, None]
        assert [role.game_role_id for role in ark_roles if role.is_local_default] == ["existing-ark"]
        assert [role.game_role_id for role in ef_roles if role.is_local_default] == ["ef-role-a"]
        assert set(plan.planned_defaults) == {"arknights", "endfield"}


@pytest.mark.asyncio
async def test_bound_roles_template_escapes_public_role_data_and_supports_all_modes(app):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_skland.account import build_bound_roles_plan
    from nonebot_plugin_skland.schemas import BoundRolesCard, BoundRoleCardAccount, BindingAccountSnapshot

    template = _bound_roles_template()

    async with get_session() as session:
        snapshot = BindingAccountSnapshot.from_apps("remote-account-two-long", _binding_apps())
        plan = await build_bound_roles_plan(
            200,
            session,
            mode="bind_confirmation",
            pending_snapshot=snapshot,
        )
        await session.rollback()

    titles = {
        "overview": "角色档案",
        "bind_confirmation": "确认绑定角色",
        "unbind_selection": "选择解绑账号",
        "unbind_confirmation": "解绑确认",
    }
    states = {
        "overview": ("bound", "已绑定"),
        "bind_confirmation": ("pending_bind", "待绑定"),
        "unbind_selection": ("bound", "已绑定"),
        "unbind_confirmation": ("pending_unbind", "待解绑"),
    }
    public_uids = (
        "ark-123456789012345678901234567890",
        "deleted-role",
        "ef-role-a",
        "ef-role-b",
    )
    public_server_names = ("\u5b98\u670d", "B\u670d", "\u56fd\u670d", "\u54e8\u7ad9\u4e59")
    hidden_values = (
        "remote-account-two-long",
        "••••long",
        "endfield-parent",
        "China",
        "1001",
        "1002",
        "2001",
        "2002",
        "20",
        "10",
    )
    obsolete_labels = ("Server", "ROLE ID", "BINDING UID", "PERSONAL RECORD", "DEMO")

    for mode, title in titles.items():
        account_data = model_dump(plan.card.accounts[0])
        account_data["index"] = 17
        account_data["state"] = states[mode][0]
        card = BoundRolesCard(
            mode=mode,
            accounts=[BoundRoleCardAccount(**account_data)],
        )
        rendered = template.render(props=card)
        assert "Doctor &lt;Main&gt;" in rendered
        assert "Doctor <Main>" not in rendered
        visible = _visible_text(rendered)

        assert title in visible
        assert "森空岛" in visible
        assert "账号" in visible
        assert "17" in visible
        assert states[mode][1] in visible
        assert "Generated by nonebot-plugin-skland" in visible
        if mode == "overview":
            assert "sk char set ark" in visible
            assert "sk char set ef" in visible
        assert "Doctor <Main>" in visible
        assert visible.count("Admin") == 2
        assert all(value in visible for value in public_uids)
        assert all(value in visible for value in public_server_names)
        assert "插件默认" in visible
        assert "森空岛默认" in visible
        visible_casefold = visible.casefold()
        assert all(label.casefold() not in visible_casefold for label in obsolete_labels)
        assert "角色已删除" in visible
        assert "角色已封禁" in visible
        assert all(not _contains_visible_token(visible, value) for value in hidden_values)

    pending_update_data = model_dump(plan.card.accounts[0])
    pending_update_data["index"] = 17
    pending_update_data["state"] = "pending_update"
    pending_update = BoundRolesCard(
        mode="bind_confirmation",
        accounts=[BoundRoleCardAccount(**pending_update_data)],
    )
    assert "待更新" in _visible_text(template.render(props=pending_update))


def test_bound_roles_template_renders_empty_accounts_and_games(app):
    from nonebot_plugin_skland.schemas import BoundRolesCard, BoundRoleCardAccount

    template = _bound_roles_template()

    empty_overview = _visible_text(template.render(props=BoundRolesCard(mode="overview", accounts=[])))
    assert "尚未绑定森空岛账号" in empty_overview

    empty_account = BoundRoleCardAccount(
        account_id=None,
        index=1,
        account_user_id=None,
        account_hint="待同步",
        state="pending_bind",
        roles=[],
    )
    empty_games = _visible_text(
        template.render(
            props=BoundRolesCard(mode="bind_confirmation", accounts=[empty_account]),
        )
    )
    assert "森空岛" in empty_games
    assert "账号" in empty_games
    assert "待绑定" in empty_games
    assert "明日方舟" in empty_games
    assert "明日方舟：终末地" in empty_games
    assert empty_games.count("暂无角色") == 2
    assert "暂无可绑定的角色，不会保存账号" in empty_games
    assert "待同步" not in empty_games
