import re
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
            server_name="1",
            nickname="默认角色",
            is_skland_default=False,
        )
        selected_role = Character(
            account_id=selected_account.id,
            app_code="arknights",
            uid="selected-uid",
            role_id="selected-uid",
            channel_master_id="2",
            server_name="2",
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

    async def render(view, *, show_all):
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
            await case.command.garrison_handler(*args, role_index=2, show_all=True)
        assert "done" not in case.reactions
    else:
        await case.command.garrison_handler(*args, role_index=2, show_all=True)
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


@pytest.mark.parametrize(
    ("options", "prefix", "expected_pages"),
    [
        ("", "recent", [[1, 2, 3, 4]]),
        ("-a", "recent", [[1, 2, 3, 4], [5]]),
        ("--all", "recent", [[1, 2, 3, 4], [5]]),
        ("-f", "favorite", [[1, 2, 3, 4]]),
        ("-f -a", "favorite", [[1, 2, 3, 4], [5, 6]]),
        ("-f --all", "favorite", [[1, 2, 3, 4], [5, 6]]),
        ("-i 5", "recent", [[5]]),
        ("-a -i 5", "recent", [[5]]),
        ("-f -i 6", "favorite", [[6]]),
        ("-f -a -i 6", "favorite", [[6]]),
    ],
)
async def test_selected_list_pagination_preserves_full_statistics(
    garrison_case, mocker, options, prefix, expected_pages
):
    from nonebot.compat import model_dump
    from nonebot_plugin_alconna import Image, Match

    from nonebot_plugin_skland import render
    from nonebot_plugin_skland.compact import template_to_html
    from nonebot_plugin_skland.matcher import skland_command
    from nonebot_plugin_skland.schemas.arknights.garrison import GarrisonRecord

    case = garrison_case
    data, resources = _garrison_payloads()
    source = model_dump(data.history.records[0])
    data.history.records = [GarrisonRecord(**{**source, "id": f"recent-{index}"}) for index in range(1, 6)]
    data.history.favourRecords = [GarrisonRecord(**{**source, "id": f"favorite-{index}"}) for index in range(1, 7)]
    data.gameUserInfo.name = "测试 & 博士"
    mocker.patch.object(case.command, "fetch_garrison", return_value=(data, resources, "act-current"))
    mocker.patch.object(type(case.user_session), "platform", new_callable=mocker.PropertyMock, return_value="Discord")

    async def render_html(*, template_path, template_name, templates, filters, **kwargs):
        html = await template_to_html(template_path, template_name, filters=filters, **templates)
        return html.encode()

    mocker.patch.object(render, "template_to_pic", new=render_html)
    result = skland_command.parse(f"/skland garrison -r 2 {options}")
    assert result.matched
    await case.command.garrison_handler(
        case.user_session,
        case.session,
        Match(0, available=False),
        mocker.Mock(self_id="bot"),
        role_index=result.query("garrison.role.role_index"),
        record_index=result.query("garrison.index.record_index"),
        favored=result.find("garrison.favored"),
        show_all=result.find("garrison.all"),
    )
    pages = [message[Image][0].raw.decode() for message in case.messages]
    assert [re.findall(r'data-record-id="([^"]+)"', html) for html in pages] == [
        [f"{prefix}-{index}" for index in indices] for indices in expected_pages
    ]
    assert all("bilibili服" in html for html in pages)
    assert all("测试 &amp; 博士" in html for html in pages)
    assert case.reactions[-1] == "done"
    if not result.find("garrison.index"):
        assert re.findall(r'class="garrison-preference-count"><strong>(\d+)</strong>', pages[0]) == ["5"]
        assert "#01" in pages[0]
        assert "1 / 2" in pages[0]
        if len(pages) == 2:
            assert "#05" in pages[1]
            assert "2 / 2" in pages[1]
            assert '<section class="garrison-summary ' not in pages[1]


@pytest.mark.parametrize("options", ["--activity act-current", "-a act-current"])
def test_garrison_rejects_removed_activity_selection(app, options):
    from nonebot_plugin_skland.matcher import skland_command

    assert not skland_command.parse(f"/skland garrison {options}").matched


@pytest.mark.parametrize(
    ("image_count", "expected_sizes"),
    [(2, [2]), (16, [16]), (17, [16, 1]), (32, [16, 16]), (33, [16, 16, 1])],
)
async def test_forward_batches_preserve_every_image_in_order(garrison_case, mocker, image_count, expected_sizes):
    from nonebot_plugin_alconna import Image, Match, Reference

    case = garrison_case
    data, resources = _garrison_payloads()
    images = [f"page-{index}".encode() for index in range(1, image_count + 1)]
    mocker.patch.object(case.command, "fetch_garrison", return_value=(data, resources, "act-current"))
    mocker.patch.object(case.command, "render_garrison_history", return_value=images)
    mocker.patch.object(type(case.user_session), "platform", new_callable=mocker.PropertyMock, return_value="QQClient")
    await case.command.garrison_handler(
        case.user_session,
        case.session,
        Match(0, available=False),
        mocker.Mock(self_id="bot"),
        show_all=True,
    )
    batches = [message[Reference][0].children for message in case.messages]
    assert [len(batch) for batch in batches] == expected_sizes
    assert [node.content[Image][0].raw for batch in batches for node in batch] == images
    assert [node.name for batch in batches for node in batch] == [
        f"测试博士 | 卫戍战绩 {index}/{image_count}" for index in range(1, image_count + 1)
    ]
    assert case.reactions[-1] == "done"


async def test_later_forward_failure_stops_remaining_batches_without_done(garrison_case, mocker):
    from nonebot_plugin_alconna import Image, Match, Reference, UniMessage

    case = garrison_case
    data, resources = _garrison_payloads()
    images = [f"page-{index}".encode() for index in range(1, 34)]
    mocker.patch.object(case.command, "fetch_garrison", return_value=(data, resources, "act-current"))
    mocker.patch.object(case.command, "render_garrison_history", return_value=images)
    mocker.patch.object(type(case.user_session), "platform", new_callable=mocker.PropertyMock, return_value="QQClient")
    attempts = []

    async def send(message, **kwargs):
        assert not case.session.in_transaction()
        assert "done" not in case.reactions
        attempts.append(message)
        if len(attempts) == 2:
            raise RuntimeError("第二批发送失败")
        case.messages.append(message)

    mocker.patch.object(UniMessage, "send", new=send)
    with pytest.raises(RuntimeError, match="第二批发送失败"):
        await case.command.garrison_handler(
            case.user_session,
            case.session,
            Match(0, available=False),
            mocker.Mock(self_id="bot"),
            show_all=True,
        )
    attempted_batches = [message[Reference][0].children for message in attempts]
    assert [len(batch) for batch in attempted_batches] == [16, 16]
    assert [node.content[Image][0].raw for node in attempted_batches[1]] == images[16:32]
    assert [node.content[Image][0].raw for node in case.messages[0][Reference][0].children] == images[:16]
    assert len(case.messages) == 1
    assert "done" not in case.reactions
