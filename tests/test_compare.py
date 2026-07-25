"""Tests for operator training compare helpers."""

from pathlib import Path

import pytest


@pytest.fixture
def compare_helpers(app):
    from nonebot_plugin_skland.render import compare_card_scale
    from nonebot_plugin_skland.video import (
        COVER_DURATION,
        OPERATOR_FRAME_DURATION,
        write_concat_list,
    )
    from nonebot_plugin_skland.commands.compare import (
        ComparePlayer,
        aligned_operator_cards,
        dedupe_targets,
        platform_id_of,
        six_star_entries,
    )
    from nonebot_plugin_skland.schemas import OperatorCard, OperatorCatalog, OperatorCatalogEntry
    from nonebot_plugin_skland.schemas.arknights.models.status import AP, Avatar, Exp, Secretary, Status

    return {
        "compare_card_scale": compare_card_scale,
        "COVER_DURATION": COVER_DURATION,
        "OPERATOR_FRAME_DURATION": OPERATOR_FRAME_DURATION,
        "write_concat_list": write_concat_list,
        "ComparePlayer": ComparePlayer,
        "aligned_operator_cards": aligned_operator_cards,
        "dedupe_targets": dedupe_targets,
        "platform_id_of": platform_id_of,
        "six_star_entries": six_star_entries,
        "OperatorCard": OperatorCard,
        "OperatorCatalog": OperatorCatalog,
        "OperatorCatalogEntry": OperatorCatalogEntry,
        "AP": AP,
        "Avatar": Avatar,
        "Exp": Exp,
        "Secretary": Secretary,
        "Status": Status,
    }


def _entry(helpers, char_id: str, name: str, sort_id: int, rarity: int = 5):
    return helpers["OperatorCatalogEntry"](
        char_id=char_id,
        name=name,
        appellation=name,
        profession="近卫",
        rarity=rarity,
        sort_id=sort_id,
    )


def _status(helpers, uid: str, name: str):
    return helpers["Status"](
        uid=uid,
        name=name,
        level=120,
        avatar=helpers["Avatar"](type="icon", id="1", url="https://example.com/a.png"),
        registerTs=1600000000,
        mainStageProgress="1-1",
        secretary=helpers["Secretary"](charId="char_002_amiya", skinId="char_002_amiya#1"),
        resume="",
        subscriptionEnd=0,
        ap=helpers["AP"](current=100, max=120, lastApAddTime=0, completeRecoveryTime=0),
        storeTs=0,
        lastOnlineTs=0,
        charCnt=1,
        furnitureCnt=1,
        skinCnt=1,
        exp=helpers["Exp"](current=0, max=100),
    )


def test_platform_id_and_dedupe_targets(compare_helpers):
    from nonebot_plugin_alconna import At

    targets = (
        At("user", target="1001"),
        2002,
        At("user", target="1001"),
        2002,
        At("user", target="3003"),
    )
    platform_id_of = compare_helpers["platform_id_of"]
    dedupe_targets = compare_helpers["dedupe_targets"]
    assert platform_id_of(targets[0]) == "1001"
    assert platform_id_of(targets[1]) == "2002"
    assert [platform_id_of(item) for item in dedupe_targets(targets)] == ["1001", "2002", "3003"]


def test_six_star_entries_sorted_by_reverse_release(compare_helpers):
    catalog = compare_helpers["OperatorCatalog"](
        entries=(
            _entry(compare_helpers, "char_a", "A", sort_id=1, rarity=5),
            _entry(compare_helpers, "char_b", "B", sort_id=30, rarity=5),
            _entry(compare_helpers, "char_c", "C", sort_id=20, rarity=4),
            _entry(compare_helpers, "char_d", "D", sort_id=10, rarity=5),
        )
    )
    result = compare_helpers["six_star_entries"](catalog.entries)
    assert [item.char_id for item in result] == ["char_a", "char_d", "char_b"]


def test_aligned_operator_cards_fills_missing(compare_helpers):
    entry = _entry(compare_helpers, "char_350_surtr", "史尔特尔", sort_id=20)
    owned = compare_helpers["OperatorCard"].from_entry(entry, None)
    players = [
        compare_helpers["ComparePlayer"](
            status=_status(compare_helpers, "1", "one"),
            cover_bg="",
            cards_by_id={entry.char_id: owned},
        ),
        compare_helpers["ComparePlayer"](
            status=_status(compare_helpers, "2", "two"),
            cover_bg="",
            cards_by_id={},
        ),
    ]
    cards = compare_helpers["aligned_operator_cards"](players, entry)
    assert len(cards) == 2
    assert cards[0].char_id == entry.char_id
    assert cards[1].char_id == entry.char_id
    assert cards[1].owned is False


def test_write_concat_list_durations(compare_helpers, tmp_path: Path):
    frame0 = tmp_path / "frame_000.png"
    frame1 = tmp_path / "frame_001.png"
    frame2 = tmp_path / "frame_002.png"
    for path in (frame0, frame1, frame2):
        path.write_bytes(b"png")

    list_path = tmp_path / "list.txt"
    compare_helpers["write_concat_list"](
        [
            (frame0, compare_helpers["COVER_DURATION"]),
            (frame1, compare_helpers["OPERATOR_FRAME_DURATION"]),
            (frame2, compare_helpers["OPERATOR_FRAME_DURATION"]),
        ],
        list_path,
    )
    text = list_path.read_text(encoding="utf-8")
    assert f"duration {compare_helpers['COVER_DURATION']:g}" in text
    assert text.count(f"duration {compare_helpers['OPERATOR_FRAME_DURATION']:g}") == 2
    assert text.strip().endswith(f"file '{frame2.resolve().as_posix()}'")
    assert text.count(f"file '{frame2.resolve().as_posix()}'") == 2


@pytest.mark.parametrize(
    ("count", "minimum"),
    [
        (2, 1.0),
        (3, 1.0),
        (6, 0.5),
    ],
)
def test_compare_card_scale(compare_helpers, count: int, minimum: float):
    scale = compare_helpers["compare_card_scale"](count)
    assert scale >= minimum
    assert scale <= 2.4
