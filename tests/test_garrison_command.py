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
        selected_role_id = selected_role.id
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
            selected_role_id=selected_role_id,
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
    from nonebot_plugin_skland.matcher import skland_command
    from nonebot_plugin_skland.compact import template_to_html
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


async def test_overview_keeps_archived_matches_after_window_rolls(garrison_case, mocker):
    from nonebot_plugin_alconna import Match

    from nonebot_plugin_skland.services.garrison import archive_garrison_matches
    from nonebot_plugin_skland.schemas.arknights.garrison import (
        GarrisonRecord,
        GarrisonRecordBond,
        GarrisonRecordBoss,
    )

    case = garrison_case
    initial, _ = _garrison_payloads()
    earlier = GarrisonRecord(
        id="rolled-out",
        activityId="act-current",
        bandId="band-test",
        completeState=0,
        gameStartTs=100,
        gameEndTs=3700,
        bondInfo=[GarrisonRecordBond(bondId="bond-zero", layer=0, activate=1)],
        acBossInfo=[GarrisonRecordBoss(bossId="hidden", isHidden=True, isKilled=True)],
    )
    initial.history.records = [earlier, earlier]
    initial.history.favourRecords = [GarrisonRecord(id="favorite-only", activityId="act-current", bandId="band-test")]
    await archive_garrison_matches(case.session, case.selected_role_id, "act-current", initial)
    await case.session.refresh(case.user_session.user)

    live, resources = _garrison_payloads()
    live.career.totalMultiBattleCnt = 2
    live.history.favourRecords = [GarrisonRecord(id="rolled-out", activityId="act-current", completeState=1)]
    mocker.patch.object(case.command, "fetch_garrison", return_value=(live, resources, "act-current"))
    render = mocker.patch.object(case.command, "render_garrison_history", return_value=[b"image"])
    await case.command.garrison_handler(
        case.user_session, case.session, Match(0, available=False), mocker.Mock(self_id="bot"), role_index=2
    )

    view = render.await_args.args[0]
    assert [record.record_id for record in view.records] == ["record-current"]
    assert view.recent_scope == "已归档 2 场 · 官方 4 场"
    assert [(item.recent_count, item.win_percent) for item in view.strategies] == [(2, 50.0)]
    assert [(item.recent_count, item.max_layer) for item in view.bonds] == [(1, 0)]
    metrics = {metric.label: (metric.value, metric.secondary_value) for metric in view.metrics}
    assert metrics["游戏时长"][0] == "1时10分"
    assert metrics["Boss 击杀"] == ("1", "1")


@pytest.mark.parametrize(
    ("peer_count", "active_layers", "visible_bond"),
    [(3, (2, 5, 5), ("peer-bond-2", 5)), (2, (0,), ("peer-bond-1", 0)), (1, (), None)],
    ids=["three-highest-first-on-tie", "two-zero-layer-and-missing-avatar", "one-no-activated-bond"],
)
async def test_detail_lists_only_bound_teammates_from_the_same_joint_scene(
    garrison_case, mocker, peer_count, active_layers, visible_bond
):
    from nonebot_plugin_alconna import Image, Match

    from nonebot_plugin_skland import render
    from nonebot_plugin_skland.model import SkUser, Character
    from nonebot_plugin_skland.compact import template_to_html
    from nonebot_plugin_skland.schemas.arknights.models.status import Avatar
    from nonebot_plugin_skland.services.garrison import archive_garrison_matches
    from nonebot_plugin_skland.schemas.arknights.garrison import (
        GarrisonChess,
        GarrisonRecord,
        GarrisonBandBadge,
        GarrisonRecordBond,
    )

    case = garrison_case

    async def archive_peer(uid, nickname, *, avatar_url="", mode="MULTI", activity="act-current"):
        account = SkUser(owner_id=762, cred="peer-test", cred_token="peer-token")
        case.session.add(account)
        await case.session.flush()
        peer = Character(
            account_id=account.id,
            uid=uid,
            role_id=uid,
            app_code="arknights",
            channel_master_id="2",
            server_name="2",
            nickname=nickname,
        )
        case.session.add(peer)
        await case.session.flush()
        peer_data, _ = _garrison_payloads()
        peer_data.gameUserInfo.avatar = Avatar(type="icon", id="avatar-test", url=avatar_url) if avatar_url else None
        peer_data.career.bandBadges = [GarrisonBandBadge(id="band-test", masterVictor=True)]
        bonds = [
            GarrisonRecordBond(bondId=f"peer-bond-{index}", layer=layer, activate=1)
            for index, layer in enumerate(active_layers, 1)
        ]
        bonds.append(GarrisonRecordBond(bondId="inactive-bond", layer=8, activate=0))
        peer_data.history.records = [
            GarrisonRecord(
                id=f"{uid}-record",
                sceneId="shared-scene",
                modeType=mode,
                activityId=activity,
                versionId="v-current",
                bandId="band-test",
                bondInfo=bonds,
                chessSquad=[GarrisonChess(charId="peer-operator")],
            )
        ]
        await archive_garrison_matches(case.session, peer.id, activity, peer_data)

    avatars = [f"https://web.hycdn.cn/test/avatar-{index}.png" for index in range(1, peer_count + 1)]
    if peer_count == 2:
        avatars[1] = ""
    await archive_peer("peer-private-uid", "同局 <甲>", avatar_url=avatars[0])
    for index, avatar_url in enumerate(avatars[1:], 2):
        await archive_peer(f"peer-{index}", f"同局博士 {index}", avatar_url=avatar_url)
    await archive_peer("peer-private-uid", "重复绑定不展示")
    await archive_peer("solo-uid", "独立不展示", mode="SINGLE")
    await archive_peer("old-uid", "跨期不展示", activity="act-old")
    await case.session.refresh(case.user_session.user)

    live, resources = _garrison_payloads()
    live.history.records[0].modeType = "MULTI"
    live.history.records[0].sceneId = "shared-scene"
    mocker.patch.object(case.command, "fetch_garrison", return_value=(live, resources, "act-current"))

    async def render_html(*, template_path, template_name, templates, filters, **kwargs):
        return (await template_to_html(template_path, template_name, filters=filters, **templates)).encode()

    mocker.patch.object(render, "template_to_pic", new=render_html)
    await case.command.garrison_handler(
        case.user_session,
        case.session,
        Match(0, available=False),
        mocker.Mock(self_id="bot"),
        role_index=2,
        record_index=1,
    )

    html = case.messages[0][Image][0].raw.decode()
    panel = html.split('<section class="garrison-teammates"', 1)[1].split("</section>", 1)[0]
    assert "同局 &lt;甲&gt;" in panel
    assert "测试策略" in panel
    assert "title_team_logo_master.png" in panel
    assert re.findall(r'<img src="(https://web\.hycdn\.cn/test/avatar-\d+\.png)" alt=""', panel) == [
        url for url in avatars if url
    ]
    assert panel.count("<span>博士</span>") == avatars.count("")
    for index in range(2, peer_count + 1):
        assert f"同局博士 {index}" in panel
    bond_names = re.findall(r"<span>(peer-bond-\d+)</span>", panel)
    bond_layers = re.findall(r"<b>(\d+)</b>", panel)
    if visible_bond is None:
        assert not bond_names
        assert not bond_layers
    else:
        assert bond_names == [visible_bond[0]] * peer_count
        assert bond_layers == [str(visible_bond[1])] * peer_count
    assert all(
        text not in panel
        for text in ("inactive-bond", "peer-operator", "重复绑定不展示", "独立不展示", "跨期不展示", "临时角色")
    )
    assert "peer-private-uid" not in html


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
