"""Unit tests for operator box / book roster helpers."""

from urllib.parse import unquote


def test_parse_stars_default_and_all(app):
    from nonebot_plugin_skland.roster import parse_stars

    assert parse_stars(None) == frozenset({6})
    assert parse_stars("") == frozenset({6})
    assert parse_stars("all") == frozenset(range(1, 7))
    assert parse_stars("5,6") == frozenset({5, 6})
    assert parse_stars("6星") == frozenset({6})
    assert parse_stars("4-6") == frozenset({4, 5, 6})
    assert parse_stars("6-4") == frozenset({4, 5, 6})


def test_parse_professions(app):
    from nonebot_plugin_skland.roster import parse_professions

    assert parse_professions(None) == frozenset()
    assert parse_professions("先锋,近卫") == frozenset({"先锋", "近卫"})
    assert parse_professions("caster") == frozenset({"术师"})


def test_rarity_and_profession_filters_on_book(app):
    from nonebot_plugin_skland.roster import (
        RosterFilter,
        build_book_cards,
        load_catalog,
        parse_professions,
        parse_stars,
    )

    catalog = load_catalog()
    expect_guard6 = sum(1 for c in catalog if c.star == 6 and c.profession == "近卫")
    expect_56 = sum(1 for c in catalog if c.star in {5, 6})

    guard6 = build_book_cards(
        [],
        RosterFilter(stars=parse_stars("6"), professions=parse_professions("近卫")),
    )
    assert len(guard6) == expect_guard6
    assert all(c.rarity == 5 and c.profession == "近卫" for c in guard6)

    star56 = build_book_cards(
        [],
        RosterFilter(stars=parse_stars("5,6"), professions=frozenset()),
    )
    assert len(star56) == expect_56
    assert all(c.rarity + 1 in {5, 6} for c in star56)

    ranged = build_book_cards(
        [],
        RosterFilter(stars=parse_stars("4-6"), professions=parse_professions("术师")),
    )
    assert ranged
    assert all(c.rarity + 1 in {4, 5, 6} and c.profession == "术师" for c in ranged)


def test_box_respects_profession_filter(app):
    from nonebot_plugin_skland.roster import (
        RosterFilter,
        build_box_cards,
        default_skin_id,
        load_catalog,
        parse_professions,
        parse_stars,
    )
    from nonebot_plugin_skland.schemas.arknights.models.chars import Character as OwnedChar

    catalog = load_catalog()
    guard = next(c for c in catalog if c.star == 6 and c.profession == "近卫")
    medic = next(c for c in catalog if c.star == 6 and c.profession == "医疗")

    def owned(char_id: str) -> OwnedChar:
        return OwnedChar(
            charId=char_id,
            skinId=default_skin_id(char_id),
            level=90,
            evolvePhase=2,
            potentialRank=5,
            mainSkillLvl=7,
            skills=[],
            equip=[],
            favorPercent=100,
            defaultSkillId="",
            gainTime=0,
            defaultEquipId="",
        )

    cards = build_box_cards(
        [owned(guard.char_id), owned(medic.char_id)],
        RosterFilter(stars=parse_stars("6"), professions=parse_professions("近卫")),
    )
    assert len(cards) == 1
    assert cards[0].char_id == guard.char_id


def test_skin_portrait_url_encodes_hash_and_skin(app):
    from nonebot_plugin_skland.roster import skin_portrait_url

    url = skin_portrait_url("char_290_vigna@summer#1")
    assert "char_skin/portrait/" in url
    assert "char_290_vigna" in unquote(url)
    assert "@summer" in unquote(url) or "%40summer" in url


def test_catalog_loaded_and_sorted_newest_first(app):
    from nonebot_plugin_skland.roster import load_catalog

    catalog = load_catalog()
    assert len(catalog) >= 400
    assert catalog[0].sort_id >= catalog[-1].sort_id
    six_star = [c for c in catalog if c.star == 6]
    assert len(six_star) >= 100


def test_box_only_owned_and_default_six_star(app):
    from nonebot_plugin_skland.roster import (
        RosterFilter,
        build_box_cards,
        default_skin_id,
        load_catalog,
    )
    from nonebot_plugin_skland.schemas.arknights.models.chars import Character as OwnedChar

    catalog = load_catalog()
    sample = next(c for c in catalog if c.star == 6)
    low = next(c for c in catalog if c.star == 4)

    def owned(char_id: str, skin_id: str | None = None) -> OwnedChar:
        return OwnedChar(
            charId=char_id,
            skinId=skin_id or default_skin_id(char_id),
            level=90,
            evolvePhase=2,
            potentialRank=5,
            mainSkillLvl=7,
            skills=[],
            equip=[],
            favorPercent=100,
            defaultSkillId="",
            gainTime=0,
            defaultEquipId="",
        )

    cards = build_box_cards(
        [owned(sample.char_id, f"{sample.char_id}@summer#1"), owned(low.char_id)],
        RosterFilter(stars=frozenset({6}), professions=frozenset()),
    )
    assert len(cards) == 1
    assert cards[0].char_id == sample.char_id
    assert cards[0].owned
    assert "@summer" in unquote(cards[0].portrait)
    assert "Lv90" in cards[0].meta_text


def test_book_greys_unowned_and_uses_player_skin(app):
    from nonebot_plugin_skland.roster import (
        RosterFilter,
        build_book_cards,
        default_skin_id,
        load_catalog,
    )
    from nonebot_plugin_skland.schemas.arknights.models.chars import Character as OwnedChar

    catalog = load_catalog()
    sample = next(c for c in catalog if c.star == 6)
    owned = OwnedChar(
        charId=sample.char_id,
        skinId=f"{sample.char_id}@summer#1",
        level=90,
        evolvePhase=2,
        potentialRank=5,
        mainSkillLvl=7,
        skills=[],
        equip=[],
        favorPercent=100,
        defaultSkillId="",
        gainTime=0,
        defaultEquipId="",
    )
    cards = build_book_cards([owned], RosterFilter(stars=frozenset({6}), professions=frozenset()))
    assert len(cards) >= 100
    owned_card = next(c for c in cards if c.char_id == sample.char_id)
    unowned_card = next(c for c in cards if not c.owned)
    assert owned_card.owned
    assert "@summer" in unquote(owned_card.portrait)
    assert not unowned_card.owned
    assert unowned_card.skin_id == default_skin_id(unowned_card.char_id)
    assert unowned_card.meta_text == ""


def test_skill_level_label(app):
    from nonebot_plugin_skland.roster import skill_level_label

    assert skill_level_label(7, 0) == "7"
    assert skill_level_label(7, 3) == "专3"
    assert skill_level_label(4, 0) == "4"


def test_skills_match_operator_catalog(app):
    from nonebot_plugin_skland.roster import RosterFilter, build_book_cards, load_catalog
    from nonebot_plugin_skland.schemas.arknights.models.chars import Character as OwnedChar
    from nonebot_plugin_skland.schemas.arknights.models.chars import Skill

    entry = next(c for c in load_catalog() if c.char_id == "char_350_surtr")
    assert entry.skill_ids == ("skchr_surtr_1", "skchr_surtr_2", "skchr_surtr_3")
    owned = OwnedChar(
        charId=entry.char_id,
        skinId=f"{entry.char_id}#1",
        level=90,
        evolvePhase=2,
        potentialRank=5,
        mainSkillLvl=7,
        skills=[Skill(id="skchr_surtr_3", specializeLevel=3)],
        equip=[],
        favorPercent=100,
        defaultSkillId="",
        gainTime=0,
        defaultEquipId="",
    )
    cards = build_book_cards([owned], RosterFilter(stars=frozenset({6}), professions=frozenset(), name="史尔特尔"))
    assert len(cards) == 1
    assert "skchr_surtr_3" in cards[0].skills[0].icon
    assert cards[0].skills[0].specialize_level == 3
    assert cards[0].skills[0].mastered


def test_modules_match_operator_catalog(app):
    from nonebot_plugin_skland.roster import RosterFilter, build_book_cards, load_catalog
    from nonebot_plugin_skland.schemas.arknights.models.assist_chars import Equipment
    from nonebot_plugin_skland.schemas.arknights.models.base import Equip
    from nonebot_plugin_skland.schemas.arknights.models.chars import Character as OwnedChar

    entry = next(c for c in load_catalog() if c.char_id == "char_350_surtr")
    assert [m.type_icon for m in entry.modules] == ["original", "aft-x", "aft-y"]
    owned = OwnedChar(
        charId=entry.char_id,
        skinId=f"{entry.char_id}#1",
        level=90,
        evolvePhase=2,
        potentialRank=5,
        mainSkillLvl=7,
        skills=[],
        equip=[
            Equip(id="uniequip_001_surtr", level=1, locked=False),
            Equip(id="uniequip_002_surtr", level=3, locked=False),
            Equip(id="uniequip_003_surtr", level=0, locked=True),
        ],
        favorPercent=100,
        defaultSkillId="",
        gainTime=0,
        defaultEquipId="uniequip_002_surtr",
    )
    equipment_map = {m.id: Equipment(id=m.id, name=m.id, typeIcon=m.type_icon) for m in entry.modules}
    cards = build_book_cards(
        [owned],
        RosterFilter(stars=frozenset({6}), professions=frozenset(), name="史尔特尔"),
        equipment_map=equipment_map,
    )
    assert len(cards) == 1
    assert len(cards[0].modules) == 2
    assert "aft-x" in cards[0].modules[0].icon
    assert cards[0].modules[0].selected is True
    assert cards[0].modules[0].level == 3
    assert cards[0].modules[1].locked is True

    mcnist = next(c for c in load_catalog() if c.char_id == "char_4230_mcnist")
    book = build_book_cards([], RosterFilter(stars=frozenset({6}), professions=frozenset(), name="机械师"))
    assert len(book) == 1
    assert len(book[0].modules) == 1
    assert len(mcnist.modules) == 2
    assert "so-a" in book[0].modules[0].icon
    assert all(m.locked for m in book[0].modules)


def test_name_filter(app):
    from nonebot_plugin_skland.roster import CatalogEntry, RosterFilter

    entry = CatalogEntry(
        char_id="char_002_amiya",
        name="阿米娅",
        appellation="Amiya",
        profession="术师",
        rarity=4,
        sort_id=10,
        logo="罗德岛",
    )
    assert RosterFilter(stars=frozenset({5}), professions=frozenset(), name="amiya").match(entry)
    assert not RosterFilter(stars=frozenset({5}), professions=frozenset({"近卫"}), name="").match(entry)
