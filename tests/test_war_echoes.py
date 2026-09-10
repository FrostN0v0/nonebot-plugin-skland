import pytest


def _dungeon(name: str, *, passed: bool, pass_time: str = "") -> dict:
    return {
        "id": name,
        "name": name,
        "isPass": passed,
        "bestRecord": {
            "chars": [
                {
                    "charId": "chr_test",
                    "level": 90,
                    "avatarUrl": "https://example.com/avatar.png",
                    "property": {"key": "char_property_natural", "value": "自然"},
                    "rarity": {"key": "rarity_6", "value": "6"},
                    "evolvePhase": 4,
                }
            ],
            "passTs": pass_time,
        }
        if pass_time
        else None,
    }


def _war_echoes_data():
    from nonebot_plugin_skland.schemas import WarEchoes

    raw = {
        "seasons": [
            {
                "id": "3",
                "name": "虚像赛季",
                "startTs": "100",
                "endTs": "400",
                "stars": 9,
                "allPlusTasks": True,
                "weeks": [
                    {
                        "id": "2",
                        "name": "虚像轮换Ⅱ",
                        "startTs": "250",
                        "endTs": "400",
                        "stars": 7,
                        "dungeonGroups": [],
                    },
                    {
                        "id": "1",
                        "name": "虚像轮换Ⅰ",
                        "startTs": "100",
                        "endTs": "249",
                        "stars": 9,
                        "allPlusTasks": True,
                        "dungeonGroups": [
                            {
                                "name": "方阵庇护",
                                "star": 3,
                                "plusTask": True,
                                "normalDungeon": _dungeon("normal", passed=True),
                                "hardDungeon": _dungeon("hard", passed=True),
                                "cruelDungeon": _dungeon("cruel", passed=True, pass_time="57"),
                            }
                        ],
                    },
                ],
            },
            {"id": "2", "name": "谵妄赛季", "weeks": [{"id": "1", "name": "谵妄轮换"}]},
        ],
        "achieves": [
            {"name": "金", "star": 3, "firstPassTs": "10"},
            {"name": "银", "star": 2, "firstPassTs": "20"},
            {"name": "铜", "star": 1, "firstPassTs": "30"},
            {"name": "未获得", "star": 3, "firstPassTs": "0"},
        ],
    }

    return WarEchoes.model_validate(raw)


def test_view_selects_active_week_and_projects_official_ratings(app):
    from nonebot_plugin_skland.schemas import WarEchoesView

    view = WarEchoesView.from_data(_war_echoes_data(), now=150)

    assert view.season.id == "3"
    assert view.season.rating == "S+"
    assert view.week.id == "1"
    assert view.week.rating == "S+"
    assert view.week.dungeonGroups[0].selected_dungeon is not None
    assert view.week.dungeonGroups[0].selected_dungeon.id == "cruel"
    assert view.week.dungeonGroups[0].selected_dungeon.bestRecord is not None
    assert view.week.dungeonGroups[0].selected_dungeon.bestRecord.passTs == "57"
    assert view.honor.model_dump() == {"gold": 1, "silver": 2, "bronze": 3}


def test_view_accepts_explicit_season_and_week_and_rejects_unknown_values(app):
    from nonebot_plugin_skland.schemas import WarEchoesView

    view = WarEchoesView.from_data(_war_echoes_data(), season_id=2, week_id=1)
    assert (view.season.name, view.week.name) == ("谵妄赛季", "谵妄轮换")

    with pytest.raises(ValueError, match="可选赛季"):
        WarEchoesView.from_data(_war_echoes_data(), season_id=9)
    with pytest.raises(ValueError, match="可选轮换"):
        WarEchoesView.from_data(_war_echoes_data(), week_id=9)


@pytest.mark.asyncio
async def test_command_renders_selected_war_echoes_after_releasing_transaction(app, mocker, make_user_session):
    from nonebot_plugin_orm import get_session
    from nonebot_plugin_alconna import Image, Match, UniMessage

    from nonebot_plugin_skland.model import SkUser, Character
    import nonebot_plugin_skland.commands.endfield.war_echoes as command
    from nonebot_plugin_skland.db_handler import set_default_character

    async with get_session() as session:
        account = SkUser(
            owner_id=901,
            skland_user_id="remote-user",
            access_token="access",
            cred="cred",
            cred_token="token",
        )
        session.add(account)
        await session.flush()
        character = Character(
            account_id=account.id,
            uid="binding",
            role_id="role-1",
            app_code="endfield",
            channel_master_id="1",
            server_name="China",
            nickname="管理员",
            level=60,
            is_skland_default=False,
        )
        session.add(character)
        await session.flush()
        await set_default_character(901, "endfield", character.id, session)  # pyright: ignore[reportArgumentType]
        user_session = await make_user_session(session, 901)
        session.sync_session.expire_on_commit = True
        messages = []

        async def render(view):
            assert not session.in_transaction()
            assert (view.season.id, view.week.id) == ("3", "1")
            return b"war-echoes"

        async def send(message, **kwargs):
            assert not session.in_transaction()
            messages.append(message)

        api = mocker.patch.object(command.SklandAPI, "endfield_war_echoes", return_value=_war_echoes_data())
        mocker.patch.object(command, "render_ef_war_echoes", new=render)
        mocker.patch.object(command, "send_reaction")
        mocker.patch.object(UniMessage, "send", new=send)

        await command.ef_war_echoes_handler(
            user_session,
            session,  # pyright: ignore[reportArgumentType]
            Match(0, available=False),
            season_id=3,
            week_id=1,
        )

        api.assert_awaited_once()
        assert api.await_args.kwargs == {
            "user_id": "remote-user",
            "role_id": "role-1",
            "server_id": "1",
        }
        assert len(messages) == 1
        assert messages[0][Image][0].raw == b"war-echoes"
