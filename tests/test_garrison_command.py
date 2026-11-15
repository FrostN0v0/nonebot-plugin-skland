from types import SimpleNamespace

import pytest


def _garrison_payloads():
    from nonebot.compat import type_validate_python

    from nonebot_plugin_skland.schemas import GarrisonData, GarrisonResources

    record = {
        "id": "record-current",
        "activityId": "act-current",
        "versionId": "v-current",
        "completeState": 1,
        "teamComplete": 1,
        "modeType": "SINGLE",
        "modeDifficulty": "NORMAL",
        "mode": "标准模拟",
        "gameStartTs": "1700000000",
        "gameEndTs": "1700000600",
        "passRound": 14,
        "bandId": "band-test",
        "chessSquad": [],
        "bondInfo": [],
        "acBossInfo": [],
        "events": [],
    }
    data = type_validate_python(
        GarrisonData,
        {
            "currentTs": "1700000600",
            "history": {"records": [record], "favourRecords": []},
            "career": {
                "medal": {"current": 0, "count": 10},
                "bp": {"current": 100, "count": 6000},
                "totalSingleBattleCnt": 2,
                "totalSingleBattleWinCnt": 1,
            },
            "gameUserInfo": {
                "name": "测试博士",
                "level": 120,
                "avatar": {"type": "icon", "id": "avatar-test", "url": ""},
                "registerTs": "1600000000",
                "isOfficial": True,
            },
        },
    )
    resources = type_validate_python(
        GarrisonResources,
        {
            "resources": [
                {
                    "versionInfo": {
                        "activityId": "act-current",
                        "versionId": "v-current",
                        "seasonName": "测试赛季",
                        "startTime": "1600000000",
                        "endTime": "1900000000",
                    },
                    "bandInfo": {"band-test": {"id": "band-test", "name": "测试策略", "icon": "", "desc": ""}},
                }
            ]
        },
    )
    return data, resources


@pytest.fixture
async def garrison_case(app, mocker, make_user_session):
    from nonebot_plugin_orm import get_session
    from nonebot_plugin_alconna import UniMessage

    import nonebot_plugin_skland.commands.garrison as command
    from nonebot_plugin_skland.model import SkUser, Character
    from nonebot_plugin_skland.db_handler import set_default_character

    async with get_session() as session:
        default_account = SkUser(owner_id=761, cred="default-cred", cred_token="default-token")
        selected_account = SkUser(owner_id=761, cred="selected-cred", cred_token="old-token")
        session.add_all([default_account, selected_account])
        await session.flush()
        default_role = Character(
            account_id=default_account.id,
            app_code="arknights",
            uid="default-uid",
            role_id="default-uid",
            channel_master_id="1",
            server_name="官服",
            nickname="默认角色",
            is_skland_default=False,
        )
        selected_role = Character(
            account_id=selected_account.id,
            app_code="arknights",
            uid="selected-uid",
            role_id="selected-uid",
            channel_master_id="2",
            server_name="bilibili服",
            nickname="临时角色",
            is_skland_default=False,
        )
        session.add_all([default_role, selected_role])
        await session.flush()
        await set_default_character(761, "arknights", default_role.id, session)
        selected_account_id = selected_account.id
        default_role_id = default_role.id
        user_session = await make_user_session(session, 761)
        session.sync_session.expire_on_commit = True
        messages, reactions = [], []

        async def send(message, **kwargs):
            assert not session.in_transaction()
            messages.append(message)

        mocker.patch.object(UniMessage, "send", new=send)
        mocker.patch.object(command, "send_reaction", side_effect=lambda user, stage: reactions.append(stage))
        yield SimpleNamespace(
            command=command,
            session=session,
            user_session=user_session,
            selected_account_id=selected_account_id,
            default_role_id=default_role_id,
            messages=messages,
            reactions=reactions,
        )


@pytest.mark.parametrize("platform", ["QQClient", "Discord"])
@pytest.mark.parametrize("failure", [None, "render", "send"])
async def test_selected_account_refresh_is_saved_before_render_or_send(garrison_case, mocker, platform, failure):
    from nonebot_plugin_alconna import Image, Match, UniMessage

    from nonebot_plugin_skland.model import SkUser
    from nonebot_plugin_skland.api import SklandAPI, SklandLoginAPI
    from nonebot_plugin_skland.exception import UnauthorizedException
    from nonebot_plugin_skland.db_handler import get_default_character

    case = garrison_case
    data, resources = _garrison_payloads()
    mocker.patch.object(type(case.user_session), "platform", new_callable=mocker.PropertyMock, return_value=platform)

    async def get_resources(cred, *, activity_id=None):
        assert cred.cred == "selected-cred"
        return resources

    async def get_info(cred, *, uid, activity_id):
        assert (cred.cred, uid, activity_id) == ("selected-cred", "selected-uid", "act-current")
        if cred.token == "old-token":
            raise UnauthorizedException("签名已过期")
        return data

    mocker.patch.object(SklandAPI, "ark_garrison_resources", new=get_resources)
    mocker.patch.object(SklandAPI, "ark_garrison", new=get_info)
    refresh = mocker.patch.object(SklandLoginAPI, "refresh_token", return_value="fresh-token")

    async def render(view):
        assert not case.session.in_transaction()
        assert (view.uid, view.server_name, view.activity_id) == ("selected-uid", "bilibili服", "act-current")
        assert view.records[0].record_id == "record-current"
        if failure == "render":
            raise RuntimeError("渲染失败")
        return [b"first-page", b"second-page"]

    async def send(message, **kwargs):
        assert not case.session.in_transaction()
        if failure == "send":
            raise RuntimeError("发送失败")
        case.messages.append(message)

    nodes = mocker.patch.object(case.command, "CustomNode", wraps=case.command.CustomNode)
    mocker.patch.object(case.command, "render_garrison_history", new=render)
    mocker.patch.object(UniMessage, "send", new=send)
    args = (case.user_session, case.session, Match(0, available=False), mocker.Mock(self_id="bot"))
    if failure:
        with pytest.raises(RuntimeError, match="失败"):
            await case.command.garrison_handler(*args, role_index=2)
        assert "done" not in case.reactions
    else:
        await case.command.garrison_handler(*args, role_index=2)
        assert case.reactions[-1] == "done"
        if platform == "QQClient":
            assert [call.args[2][Image][0].raw for call in nodes.call_args_list] == [b"first-page", b"second-page"]
        else:
            assert [message[Image][0].raw for message in case.messages] == [b"first-page", b"second-page"]
    refresh.assert_awaited_once_with("selected-cred")
    saved_account = await case.session.get(SkUser, case.selected_account_id)
    assert saved_account.cred_token == "fresh-token"
    default_role = await get_default_character(761, "arknights", case.session)
    assert default_role.id == case.default_role_id


async def test_empty_favorites_do_not_fall_back_to_recent_record(garrison_case, mocker):
    from nonebot_plugin_alconna import Match

    case = garrison_case
    data, resources = _garrison_payloads()
    mocker.patch.object(case.command, "fetch_garrison", return_value=(data, resources, "act-current"))
    render = mocker.patch.object(case.command, "render_garrison_history")
    await case.command.garrison_handler(
        case.user_session,
        case.session,
        Match(0, available=False),
        mocker.Mock(self_id="bot"),
        role_index=2,
        record_index=1,
        favored=True,
    )
    render.assert_not_awaited()
    assert "收藏" in case.messages[0].extract_plain_text()
    assert not case.session.in_transaction()
