import json
from types import SimpleNamespace

import pytest


@pytest.fixture
def rogue_data_factory(app):
    from nonebot.compat import type_validate_python

    from nonebot_plugin_skland.schemas import RogueData

    def record(record_id):
        return {
            "id": record_id,
            "modeGrade": 0,
            "mode": "普通",
            "success": 1,
            "lastChars": [],
            "initChars": [],
            "troopChars": [],
            "gainRelicList": [],
            "cntCrossedZone": 0,
            "cntArrivedNode": 0,
            "cntBattleNormal": 0,
            "cntBattleElite": 0,
            "cntBattleBoss": 0,
            "cntGainRelicItem": 0,
            "cntRecruitUpgrade": 0,
            "totemList": [],
            "seed": "seed",
            "tagList": [],
            "lastStage": "终点",
            "score": 0,
            "band": {"id": "band", "name": "分队"},
            "startTs": "1700000000",
            "endTs": "1700000100",
            "endingText": "[]",
            "isCollect": record_id.startswith("favored"),
        }

    def create(*, record_count=2, favorite_count=1):
        return type_validate_python(
            RogueData,
            {
                "topics": [
                    {"id": "rogue_3", "isSelected": True, "name": "萨米", "pic": "https://example.com/topic.png"}
                ],
                "history": {
                    "medal": {"count": 0, "current": 0},
                    "modeGrade": 0,
                    "mode": "普通",
                    "score": 0,
                    "bpLevel": 0,
                    "chars": [],
                    "tagList": [],
                    "records": [record(f"recent-{index + 1}") for index in range(record_count)],
                    "favourRecords": [record(f"favored-{index + 1}") for index in range(favorite_count)],
                },
                "gameUserInfo": {
                    "name": "博士",
                    "level": 1,
                    "avatar": {"type": "ASSISTANT", "id": "char_test", "url": "https://example.com/avatar.png"},
                    "isOfficial": True,
                },
                "itemInfo": {},
                "userCharInfo": {},
                "career": {
                    "clearInfo": {"difficulty": "普通", "grade": 0, "endings": []},
                    "invest": 0,
                    "gold": 0,
                    "node": 0,
                    "hope": 0,
                    "upgrade": 0,
                    "sacrifice": 0,
                    "expedition": 0,
                    "chaosGain": 0,
                    "chaosLost": 0,
                    "game": 0,
                    "friend": 0,
                    "abyss": 0,
                    "totem": 0,
                    "totemUse": 0,
                    "enchant": 0,
                    "relic": 0,
                    "color": {},
                    "predict": {"totem": 0, "chaos": 0},
                    "travel": 0,
                    "step": 0,
                    "history": 0,
                    "explore": 0,
                    "memory": 0,
                    "protect": 0,
                    "alchemy": {"shield": 0, "relic": 0, "population": 0},
                    "fragment": {"wish": 0, "inspiration": 0, "idea": 0},
                    "visions": [],
                    "modeStop": {},
                    "wish": 0,
                    "variation": 0,
                    "mutation": 0,
                    "diceTrend": [],
                    "dice": 0,
                    "coin": 0,
                    "cost": 0,
                    "endingSanList": {},
                },
            },
        )

    return create


@pytest.fixture
async def rginfo_case(app, mocker, make_user_session):
    from nonebot.compat import model_dump
    from nonebot_plugin_orm import get_session
    from nonebot_plugin_alconna import Match, UniMessage

    import nonebot_plugin_skland.commands.rogue as rogue

    async with get_session() as session:
        user_session = await make_user_session(session, 980)
        messages = []

        async def send(message, **_kwargs):
            assert not session.in_transaction()
            messages.append(message)

        mocker.patch.object(UniMessage, "send", new=send)
        reaction = mocker.patch.object(rogue, "send_reaction")
        render = mocker.patch.object(rogue, "render_rogue_info", new=mocker.AsyncMock(return_value=b"details"))
        background = mocker.patch.object(
            rogue, "get_rogue_background_image", new=mocker.AsyncMock(return_value="https://example.com/background.png")
        )
        fetch = mocker.patch.object(rogue, "_get_rogue_data", new=mocker.AsyncMock())
        mocker.patch.object(
            rogue,
            "check_user_character",
            new=mocker.AsyncMock(
                return_value=(SimpleNamespace(skland_user_id="remote"), SimpleNamespace(uid="selected-uid"))
            ),
        )
        argot = mocker.Mock()
        mocker.patch.object(rogue, "get_argot", new=mocker.AsyncMock(return_value=argot))

        async def invoke(data, index, *, favored, role_index):
            ext = mocker.Mock()
            if role_index is None:
                ext.get_reply.return_value = SimpleNamespace(id="overview-message")
                argot.dump_segment.return_value = UniMessage.text(json.dumps(model_dump(data))).dump()
            else:
                ext.get_reply.return_value = None
                fetch.return_value = data
            result = mocker.Mock()
            result.find.return_value = favored
            await rogue.rginfo_handler(
                Match(index, available=True),
                "details-message",
                ext,
                result,
                user_session,
                session,
                role_index=role_index,
            )

        yield SimpleNamespace(
            invoke=invoke,
            user_session=user_session,
            messages=messages,
            reaction=reaction,
            render=render,
            background=background,
            image_type=rogue.Image,
        )


@pytest.mark.parametrize("role_index", [None, 2], ids=["reply", "selected-role"])
@pytest.mark.parametrize(
    ("index", "favored", "record_count", "favorite_count", "feedback"),
    [
        (0, False, 2, 1, "最近战绩编号应为 1-2"),
        (-1, False, 2, 1, "最近战绩编号应为 1-2"),
        (3, False, 2, 1, "最近战绩编号应为 1-2"),
        (0, True, 2, 1, "收藏战绩编号应为 1-1"),
        (-1, True, 2, 1, "收藏战绩编号应为 1-1"),
        (2, True, 2, 1, "收藏战绩编号应为 1-1"),
        (1, True, 2, 0, "暂无收藏战绩"),
        (1, False, 0, 1, "暂无最近战绩"),
    ],
)
@pytest.mark.asyncio
async def test_invalid_rogue_record_does_not_render(
    rogue_data_factory, rginfo_case, role_index, index, favored, record_count, favorite_count, feedback
):
    data = rogue_data_factory(record_count=record_count, favorite_count=favorite_count)

    await rginfo_case.invoke(data, index, favored=favored, role_index=role_index)

    rginfo_case.render.assert_not_awaited()
    rginfo_case.background.assert_not_awaited()
    rginfo_case.reaction.assert_called_once_with(rginfo_case.user_session, "unmatch")
    assert [message.extract_plain_text() for message in rginfo_case.messages] == [feedback]


@pytest.mark.parametrize("role_index", [None, 2], ids=["reply", "selected-role"])
@pytest.mark.parametrize(("index", "favored", "record_id"), [(1, True, "favored-1"), (2, False, "recent-2")])
@pytest.mark.asyncio
async def test_valid_rogue_record_renders_only_the_selected_list(
    rogue_data_factory, rginfo_case, role_index, index, favored, record_id
):
    data = rogue_data_factory()

    await rginfo_case.invoke(data, index, favored=favored, role_index=role_index)

    rginfo_case.render.assert_awaited_once()
    rendered_data, background, display_id, record, rendered_favored = rginfo_case.render.await_args.args
    selected_list = rendered_data.history.favourRecords if favored else rendered_data.history.records
    assert record is selected_list[index - 1]
    assert record.id == record_id
    assert display_id == index
    assert rendered_favored is favored
    assert background == "https://example.com/background.png"
    rginfo_case.reaction.assert_called_once_with(rginfo_case.user_session, "processing")
    assert len(rginfo_case.messages) == 1
    assert rginfo_case.messages[0][rginfo_case.image_type][0].raw == b"details"
