"""Behavior tests for the operator box and book feature."""

import json
from urllib.parse import unquote

import pytest


@pytest.fixture
def operator_catalog(app):
    from nonebot_plugin_skland.schemas import OperatorCatalog, OperatorCatalogEntry
    from nonebot_plugin_skland.schemas.arknights.game_data import OperatorCatalogModule

    return OperatorCatalog(
        entries=(
            OperatorCatalogEntry(
                char_id="char_4230_mcnist",
                name="机械师",
                appellation="Mechanist",
                profession="重装",
                rarity=5,
                sort_id=30,
                sub_profession_id="fortress",
                sub_profession_name="要塞",
                position="远程位",
                power_ids=frozenset({"elite"}),
                powers=frozenset({"罗德岛-精英干员"}),
                gender="男",
                races=frozenset({"萨卡兹"}),
                modules=(
                    OperatorCatalogModule(id="uniequip_001_mcnist", type_icon="original"),
                    OperatorCatalogModule(id="uniequip_002_mcnist", type_icon="SO-A"),
                ),
            ),
            OperatorCatalogEntry(
                char_id="char_350_surtr",
                name="史尔特尔",
                appellation="Surtr",
                profession="近卫",
                rarity=5,
                sort_id=20,
                sub_profession_id="reaper",
                sub_profession_name="收割者",
                position="近战位",
                power_ids=frozenset({"rhodes"}),
                powers=frozenset({"罗德岛"}),
                gender="女",
                races=frozenset({"萨卡兹"}),
                skill_ids=("skchr_surtr_1", "skchr_surtr_2", "skchr_surtr_3"),
                modules=(
                    OperatorCatalogModule(id="uniequip_001_surtr", type_icon="original"),
                    OperatorCatalogModule(id="uniequip_002_surtr", type_icon="AFT-X"),
                    OperatorCatalogModule(id="uniequip_003_surtr", type_icon="aft-y"),
                ),
            ),
            OperatorCatalogEntry(
                char_id="char_002_amiya",
                name="阿米娅",
                appellation="Amiya",
                profession="术师",
                rarity=4,
                sort_id=10,
                sub_profession_id="core_caster",
                sub_profession_name="中坚术师",
                position="远程位",
                power_ids=frozenset({"rhodes"}),
                powers=frozenset({"罗德岛"}),
                gender="女",
                races=frozenset({"卡特斯", "奇美拉"}),
                skill_ids=("skchr_amiya_1",),
            ),
            OperatorCatalogEntry(
                char_id="char_003_kalts",
                name="凯尔希",
                appellation="Kal'tsit",
                profession="医疗",
                rarity=5,
                sort_id=5,
                sub_profession_id="physician",
                sub_profession_name="医师",
                position="远程位",
                power_ids=frozenset({"rhodes"}),
                powers=frozenset({"罗德岛"}),
                gender="女",
                races=frozenset({"菲林"}),
            ),
            OperatorCatalogEntry(
                char_id="char_150_snakek",
                name="蛇屠箱",
                appellation="Cuora",
                profession="重装",
                rarity=3,
                sort_id=1,
                sub_profession_id="protector",
                sub_profession_name="铁卫",
                position="近战位",
                gender="女",
                races=frozenset({"佩洛"}),
            ),
        )
    )


def _owned_character(
    char_id: str,
    *,
    skin_id: str | None = None,
    skills=None,
    equipment=None,
    default_equipment_id: str = "",
):
    from nonebot_plugin_skland.schemas.arknights.models.chars import Character

    return Character(
        charId=char_id,
        skinId=skin_id or f"{char_id}#1",
        level=90,
        evolvePhase=2,
        potentialRank=5,
        mainSkillLvl=7,
        skills=skills or [],
        equip=equipment or [],
        favorPercent=100,
        defaultSkillId="",
        gainTime=0,
        defaultEquipId=default_equipment_id,
    )


def _status():
    from nonebot_plugin_skland.schemas.arknights.models.status import AP, Exp, Avatar, Status, Secretary

    return Status(
        uid="123456789",
        name="Doctor",
        level=120,
        avatar=Avatar(type="", id="", url="avatar.png"),
        registerTs=1_700_000_000,
        mainStageProgress="",
        secretary=Secretary(charId="", skinId=""),
        resume="",
        subscriptionEnd=0,
        ap=AP(current=0, max=135, lastApAddTime=0, completeRecoveryTime=0),
        storeTs=0,
        lastOnlineTs=0,
        charCnt=5,
        furnitureCnt=0,
        skinCnt=0,
        exp=Exp(current=0, max=0),
    )


def test_catalog_builds_official_fields_and_metadata(app):
    from nonebot_plugin_skland.schemas import OperatorCatalog, OperatorMetadata, OperatorMetadataSnapshot

    common = {
        "appellation": "Surtr",
        "profession": "WARRIOR",
        "rarity": 5,
        "potentialItemId": "p_char_surtr",
        "displayNumber": "R111",
        "position": "MELEE",
        "subProfessionId": "reaper",
        "mainPower": {"nationId": "rhodes", "groupId": None, "teamId": None},
        "tagList": ["输出"],
        "skills": [{"skillId": "skchr_surtr_1"}],
    }
    character_table = {
        "char_350_surtr": {"name": "史尔特尔", "isNotObtainable": False, **common},
        "char_100_old": {
            "name": "Old Operator",
            "isNotObtainable": False,
            **common,
            "potentialItemId": "p_char_old",
            "displayNumber": "R001",
            "subProfessionId": "lord",
            "position": "RANGED",
        },
        "char_999_npc": {
            "name": "NPC",
            "isNotObtainable": True,
            **common,
            "potentialItemId": "p_char_npc",
        },
    }
    patch_table = {
        "patchChars": {
            "char_1001_surtr2": {
                "name": "史尔特尔",
                "isNotObtainable": False,
                **common,
            }
        },
        "infos": {"char_350_surtr": {"tmplIds": ["char_350_surtr", "char_1001_surtr2"]}},
    }
    uniequip_table = {
        "charEquip": {"char_350_surtr": ["uniequip_001_surtr", "uniequip_002_surtr"]},
        "equipDict": {
            "uniequip_001_surtr": {"typeIcon": "original"},
            "uniequip_002_surtr": {"typeIcon": "aft-x"},
        },
    }
    handbook_table = {
        "handbookDict": {
            "char_100_old": {
                "charID": "char_100_old",
                "storyTextAudio": [{"stories": [{"storyText": "【性别】男\n【种族】菲林"}]}],
            },
            "char_350_surtr": {
                "charID": "char_350_surtr",
                "storyTextAudio": [{"stories": [{"storyText": "【性别】女\n【种族】萨卡兹"}]}],
            },
        }
    }
    metadata = OperatorMetadataSnapshot(
        operators=(
            OperatorMetadata(
                char_id="char_350_surtr",
                branch_name="收割者",
                gender="女",
                races=frozenset({"萨卡兹"}),
            ),
            OperatorMetadata(
                char_id="char_1001_surtr2",
                branch_name="收割者",
                gender="女",
                races=frozenset({"萨卡兹"}),
            ),
        )
    )

    catalog = OperatorCatalog.from_game_tables(
        character_table,
        patch_table,
        uniequip_table,
        handbook_table,
        {"rhodes": {"powerName": "罗德岛"}},
        metadata,
    )

    assert [entry.char_id for entry in catalog.entries] == [
        "char_1001_surtr2",
        "char_350_surtr",
        "char_100_old",
    ]
    assert [entry.sort_id for entry in catalog.entries] == [1, 1, 0]
    surtr = catalog.by_id["char_350_surtr"]
    assert surtr.sub_profession_name == "收割者"
    assert surtr.position == "近战位"
    assert surtr.powers == frozenset({"罗德岛"})
    assert surtr.gender == "女"
    assert surtr.races == frozenset({"萨卡兹"})
    assert surtr.skill_ids == ("skchr_surtr_1",)
    assert [module.type_icon for module in surtr.modules] == ["original", "aft-x"]
    old = catalog.by_id["char_100_old"]
    assert old.sub_profession_name == "lord"
    assert old.position == "远程位"
    assert old.gender == "男"
    assert old.races == frozenset({"菲林"})
    assert "char_999_npc" not in catalog.by_id


def test_metadata_snapshot_normalizes_and_rejects_duplicates(app):
    from nonebot_plugin_skland.schemas import OperatorMetadata, OperatorMetadataSnapshot

    snapshot = OperatorMetadataSnapshot.from_prts_rows(
        [
            {
                "title": {
                    "char_id": "char_002_amiya",
                    "branch": "中坚术师",
                    "gender": "女性",
                    "race": "卡特斯/奇美拉",
                }
            },
            {
                "title": {
                    "char_id": "char_1001_amiya2",
                    "branch": "术战者",
                    "gender": "女",
                    "race": "卡特斯/奇美拉",
                }
            },
            {
                "title": {
                    "char_id": "char_1037_amiya3",
                    "branch": "咒愈师",
                    "gender": "女",
                    "race": "未知（疑似卡特斯）",
                }
            },
        ]
    )

    assert set(snapshot.by_id) == {"char_002_amiya", "char_1001_amiya2", "char_1037_amiya3"}
    assert snapshot.by_id["char_002_amiya"].races == frozenset({"卡特斯", "奇美拉"})
    assert snapshot.by_id["char_1037_amiya3"].races == frozenset({"未知"})
    with pytest.raises(ValueError, match="duplicate char_id"):
        OperatorMetadataSnapshot(
            operators=(
                OperatorMetadata(char_id="char_duplicate"),
                OperatorMetadata(char_id="char_duplicate"),
            )
        )


@pytest.mark.asyncio
async def test_prts_metadata_fetch_paginates(app, mocker):
    from nonebot_plugin_skland.data_source import GachaTableData

    rows = [
        {
            "title": {
                "char_id": f"char_{index}",
                "branch": "Branch",
                "gender": "女",
                "race": "Race",
            }
        }
        for index in range(501)
    ]
    responses = []
    for page in (rows[:500], rows[500:]):
        response = mocker.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"cargoquery": page}
        responses.append(response)
    client = mocker.MagicMock()
    client.__aenter__ = mocker.AsyncMock(return_value=client)
    client.__aexit__ = mocker.AsyncMock(return_value=None)
    client.get = mocker.AsyncMock(side_effect=responses)
    mocker.patch("nonebot_plugin_skland.data_source.httpx.AsyncClient", return_value=client)

    fetched = await GachaTableData()._fetch_prts_operator_rows()

    assert fetched == rows
    assert [call.kwargs["params"]["offset"] for call in client.get.await_args_list] == [0, 500]


@pytest.mark.asyncio
async def test_metadata_cache_is_atomic_and_validated(app, tmp_path, monkeypatch, mocker):
    import nonebot_plugin_skland.data_source as data_source
    from nonebot_plugin_skland.exception import RequestException
    from nonebot_plugin_skland.schemas import OperatorMetadata, OperatorMetadataSnapshot

    cache_path = tmp_path / "operator_metadata.json"
    monkeypatch.setattr(data_source, "OPERATOR_METADATA_PATH", cache_path)
    original = OperatorMetadataSnapshot(operators=(OperatorMetadata(char_id="char_original", branch_name="Branch"),))
    data_source.GachaTableData._write_operator_metadata(original)
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["operators"][0]["char_id"] == "char_original"
    assert not cache_path.with_suffix(".tmp").exists()

    loader = data_source.GachaTableData()
    mocker.patch.object(
        loader,
        "_fetch_prts_operator_rows",
        new=mocker.AsyncMock(return_value=[{"title": {"char_id": "", "branch": "", "gender": "", "race": ""}}]),
    )

    with pytest.raises(RequestException):
        await loader._refresh_operator_metadata({})
    assert json.loads(cache_path.read_text(encoding="utf-8"))["operators"][0]["char_id"] == "char_original"


@pytest.mark.asyncio
async def test_load_uses_old_metadata_when_refresh_fails(app, tmp_path, monkeypatch, mocker):
    import nonebot_plugin_skland.data_source as data_source
    from nonebot_plugin_skland.exception import RequestException
    from nonebot_plugin_skland.schemas import OperatorCatalog, OperatorMetadata, OperatorMetadataSnapshot

    loader = data_source.GachaTableData()
    loader.version_file = tmp_path / "version"
    old_snapshot = OperatorMetadataSnapshot(operators=(OperatorMetadata(char_id="char_old", branch_name="Old Branch"),))
    expected_catalog = OperatorCatalog()
    monkeypatch.setattr(data_source, "DATA_ROUTES", [])
    monkeypatch.setattr(data_source, "GACHA_DATA_PATH", tmp_path)
    (tmp_path / "gacha_table.json").write_text('{"gachaPoolClient": []}', encoding="utf-8")
    mocker.patch.object(loader, "get_version", new=mocker.AsyncMock())
    mocker.patch.object(
        loader,
        "_load_operator_tables",
        return_value={"character_table.json": {}},
    )
    mocker.patch.object(loader, "_load_operator_metadata", return_value=old_snapshot)
    mocker.patch.object(
        loader,
        "_refresh_operator_metadata",
        new=mocker.AsyncMock(side_effect=RequestException("offline")),
    )
    build_catalog = mocker.patch.object(loader, "_build_operator_catalog", return_value=expected_catalog)
    mocker.patch.object(loader, "get_gacha_details", new=mocker.AsyncMock())

    updated = await loader.load(refresh_metadata=True)

    assert not updated
    assert loader.operator_catalog is expected_catalog
    build_catalog.assert_called_once_with(mocker.ANY, old_snapshot)


def test_filter_parsing_uses_or_within_and_across_dimensions(app, operator_catalog):
    from nonebot_plugin_skland.schemas import OperatorFilter

    operator_filter = OperatorFilter.from_raw(
        operator_catalog,
        rarities="5,6",
        professions="guard,medic",
        branches="reaper,医师",
        positions="近战位,远程",
        genders="女",
        factions="rhodes",
        races="萨卡兹,菲林",
    )

    matched = [entry.char_id for entry in operator_catalog.entries if operator_filter.matches(entry)]
    assert matched == ["char_350_surtr", "char_003_kalts"]
    assert operator_filter.branches == frozenset({"收割者", "医师"})
    assert operator_filter.positions == frozenset({"近战位", "远程位"})
    assert operator_filter.tags == [
        "6/5★",
        "医疗/近卫",
        "医师/收割者",
        "近战位/远程位",
        "女",
        "rhodes",
        "菲林/萨卡兹",
    ]


def test_filter_supports_multi_race_name_and_reports_unknown_values(app, operator_catalog):
    from nonebot_plugin_skland.schemas import OperatorFilter

    race_filter = OperatorFilter.from_raw(operator_catalog, rarities="5", races="奇美拉", name="amiya")
    assert [entry.char_id for entry in operator_catalog.entries if race_filter.matches(entry)] == ["char_002_amiya"]
    assert OperatorFilter.from_raw(operator_catalog).stars == frozenset({6})
    with pytest.raises(ValueError, match="未知职业分支"):
        OperatorFilter.from_raw(operator_catalog, branches="not-a-branch")


def test_box_and_book_build_from_shared_models(app, operator_catalog):
    from nonebot_plugin_skland.schemas import OperatorFilter, OperatorRoster

    surtr = _owned_character("char_350_surtr", skin_id="char_350_surtr@summer#1")
    amiya = _owned_character("char_002_amiya")
    operator_filter = OperatorFilter.from_raw(operator_catalog)

    box = OperatorRoster.build(
        status=_status(),
        catalog=operator_catalog,
        characters=[surtr, amiya],
        operator_filter=operator_filter,
    )
    assert [card.char_id for card in box.cards] == ["char_350_surtr"]
    assert box.cards[0].owned
    assert "@summer" in unquote(box.cards[0].portrait)
    assert box.cards[0].level_text == "90"
    assert box.tags[:2] == ["持有", "6★"]

    book = OperatorRoster.build(
        status=_status(),
        catalog=operator_catalog,
        characters=[surtr],
        operator_filter=operator_filter,
        book=True,
    )
    assert [card.char_id for card in book.cards] == ["char_4230_mcnist", "char_350_surtr", "char_003_kalts"]
    assert next(card for card in book.cards if card.char_id == "char_350_surtr").owned
    assert all(not card.owned for card in book.cards if card.char_id != "char_350_surtr")
    assert book.tags[:2] == ["图鉴", "6★"]


def test_skills_and_modules_reuse_existing_models(app, operator_catalog):
    from nonebot_plugin_skland.schemas import OperatorCard
    from nonebot_plugin_skland.schemas.arknights.models.base import Equip
    from nonebot_plugin_skland.schemas.arknights.models.chars import Skill
    from nonebot_plugin_skland.schemas.arknights.models.assist_chars import Equipment

    entry = operator_catalog.by_id["char_350_surtr"]
    character = _owned_character(
        entry.char_id,
        skills=[Skill(id="skchr_surtr_3", specializeLevel=3)],
        equipment=[
            Equip(id="uniequip_001_surtr", level=1, locked=False),
            Equip(id="uniequip_002_surtr", level=3, locked=False),
            Equip(id="uniequip_003_surtr", level=0, locked=True),
        ],
        default_equipment_id="uniequip_002_surtr",
    )
    equipment_map = {
        module.id: Equipment(id=module.id, name=module.id, typeIcon=module.type_icon) for module in entry.modules
    }

    card = OperatorCard.from_entry(entry, character, equipment_map)

    assert [skill.id for skill in card.skills] == ["skchr_surtr_1", "skchr_surtr_2", "skchr_surtr_3"]
    assert card.skills[2].specializeLevel == 3
    assert len(card.modules) == 2
    assert card.modules[0].icon.endswith("/aft-x.png")
    assert card.modules[0].selected
    assert card.modules[0].level == 3
    assert card.modules[1].locked


def test_shared_resource_helpers_cover_roster_and_card_models(app):
    from nonebot_plugin_skland.filters import (
        ark_rarity_icon_url,
        ark_skin_portrait_url,
        ark_uniequip_icon_url,
        ark_profession_icon_url,
    )

    portrait = ark_skin_portrait_url("char_290_vigna@summer#1")
    assert "char_skin/portrait/" in portrait
    assert "@summer" in unquote(portrait)
    assert ark_profession_icon_url("近卫").endswith("/images/profession/icon_profession_warrior.png")
    assert ark_profession_icon_url("") == ""
    assert ark_rarity_icon_url(5).endswith("/images/rarity/rarity_yellow_5.png")
    assert ark_uniequip_icon_url("AFT-X") == "https://torappu.prts.wiki/assets/uniequip_direction/aft-x.png"


def test_unified_box_command_parses_all_filters_and_removes_book_command(app):
    from nonebot_plugin_skland.matcher import skland_command

    result = skland_command.parse(
        "/skland box --book -r all -p 近卫,医疗 -b 收割者 --position 近战位 --gender 女 -f 炎 --race 萨卡兹 -n 阿米娅"
    )
    assert result.matched
    assert result.find("box.book")
    assert result.all_matched_args == {
        "rarities": "all",
        "professions": "近卫,医疗",
        "branches": "收割者",
        "positions": "近战位",
        "genders": "女",
        "factions": "炎",
        "races": "萨卡兹",
        "name": "阿米娅",
    }
    assert not skland_command.parse("/skland book").matched


@pytest.mark.asyncio
async def test_roster_render_uses_props_and_configured_timeout(app, mocker, monkeypatch, operator_catalog):
    from nonebot_plugin_skland.config import config
    from nonebot_plugin_skland.render import render_operator_roster
    from nonebot_plugin_skland.schemas import OperatorFilter, OperatorRoster

    monkeypatch.setattr(config, "roster_render_timeout", 321_000)
    render = mocker.patch(
        "nonebot_plugin_skland.render.template_to_pic",
        new=mocker.AsyncMock(return_value=b"image"),
    )
    roster = OperatorRoster(
        status=_status(),
        filter=OperatorFilter.from_raw(operator_catalog),
        cards=[],
        book=True,
    )

    result = await render_operator_roster(props=roster, background_image="background.jpg")

    assert result == b"image"
    assert render.await_args.kwargs["screenshot_timeout"] == 321_000
    assert render.await_args.kwargs["template_name"] == "operator_roster.html.jinja2"
    assert render.await_args.kwargs["device_scale_factor"] == 1.5
    assert render.await_args.kwargs["pages"]["viewport"]["width"] == 706
    assert render.await_args.kwargs["templates"]["props"] is roster
    assert render.await_args.kwargs["templates"]["background_image"] == "background.jpg"


def test_roster_config_defaults(app):
    from nonebot_plugin_skland.config import ScopedConfig

    assert ScopedConfig().roster_render_max == 16


@pytest.mark.asyncio
async def test_render_roster_pages_splits_cards(app, mocker):
    from nonebot_plugin_skland.commands.box import _render_roster_pages

    render = mocker.patch(
        "nonebot_plugin_skland.commands.box.render_operator_roster",
        new=mocker.AsyncMock(side_effect=lambda **kwargs: str(len(kwargs["props"].cards)).encode()),
    )
    roster = mocker.Mock()
    roster.cards = [mocker.Mock() for _ in range(37)]
    roster.with_cards.side_effect = lambda cards: mocker.Mock(cards=cards)

    images = await _render_roster_pages(roster=roster, background_image=None, page_size=16)

    assert images == [b"16", b"16", b"5"]
    assert [len(call.kwargs["props"].cards) for call in render.await_args_list] == [16, 16, 5]
    assert all(call.kwargs["background_image"] is None for call in render.await_args_list)


@pytest.mark.asyncio
async def test_send_roster_images_uses_qq_forward(app, mocker):
    from nonebot_plugin_skland.commands.box import _send_roster_images

    message = mocker.patch("nonebot_plugin_skland.commands.box.UniMessage")
    custom_node = mocker.patch("nonebot_plugin_skland.commands.box.CustomNode")
    message.text.return_value.send = mocker.AsyncMock()
    message.reference.return_value.send = mocker.AsyncMock()

    await _send_roster_images(
        images=[b"first", b"second", b"third"],
        total_cards=45,
        page_size=20,
        status_name="Doctor",
        user_session=mocker.Mock(platform="QQClient"),
        bot=mocker.Mock(self_id="bot"),
    )

    message.text.return_value.send.assert_awaited_once_with(reply_to=True)
    message.reference.return_value.send.assert_awaited_once_with()
    assert [call.args[1] for call in custom_node.call_args_list] == [
        "Doctor | 干员 1-20",
        "Doctor | 干员 21-40",
        "Doctor | 干员 41-45",
    ]


@pytest.mark.asyncio
async def test_send_roster_images_uses_separate_messages_elsewhere(app, mocker):
    from nonebot_plugin_skland.commands.box import _send_roster_images

    message = mocker.patch("nonebot_plugin_skland.commands.box.UniMessage")
    image_message = message.image.return_value
    image_message.send = mocker.AsyncMock()
    message.text.return_value.send = mocker.AsyncMock()

    await _send_roster_images(
        images=[b"first", b"second", b"third"],
        total_cards=45,
        page_size=20,
        status_name="Doctor",
        user_session=mocker.Mock(platform="OneBot V11"),
        bot=mocker.Mock(self_id="bot"),
    )

    message.reference.assert_not_called()
    assert image_message.send.await_count == 3


@pytest.mark.asyncio
async def test_roster_background_reuses_shared_source_for_non_default(app, monkeypatch, mocker):
    from nonebot_plugin_skland.config import config
    from nonebot_plugin_skland.commands.box import _get_roster_background_image

    get_background = mocker.patch(
        "nonebot_plugin_skland.commands.box.get_background_image",
        new=mocker.AsyncMock(return_value="background.png"),
    )
    monkeypatch.setattr(config, "background_source", "default")
    assert await _get_roster_background_image() is None
    get_background.assert_not_awaited()

    monkeypatch.setattr(config, "background_source", "random")
    assert await _get_roster_background_image() == "background.png"
    get_background.assert_awaited_once_with("ark")
