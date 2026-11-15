import pytest

_UI_BASE = "https://raw.githubusercontent.com/ArknightsAssets/ArknightsAssets2/cn/assets/dyn/ui/autochess/"
_OUTER_BASE = _UI_BASE + "%5Buc%5Dautochessouter/"
_TITLE_BASE = _OUTER_BASE + "arts/titleicon/"
_MODE_BASE = _UI_BASE + "%5Buc%5Dautochessbattle/arts/modeinfotitle/"
_SETTLEMENT_BASE = _OUTER_BASE + "settlegame/auto_chess_settle_game_state/"


@pytest.fixture
def garrison_factory(app, tmp_path, monkeypatch):
    from nonebot.compat import type_validate_python

    from nonebot_plugin_skland.schemas.arknights.garrison import GarrisonData, GarrisonView, GarrisonResources
    from nonebot_plugin_skland.config import config
    from nonebot_plugin_skland.utils import assets

    monkeypatch.setattr(config, "github_proxy_url", "")
    monkeypatch.setattr(assets, "IMAGE_DIR", tmp_path)

    def resource(version="v2", *, activity="synthetic-season", label="新版"):
        return {
            "versionInfo": {"versionId": version, "activityId": activity, "seasonName": label},
            "bandInfo": {
                "band_shared": {
                    "name": f"{label}策略",
                    "desc": "<@ba.vup>策略说明</>",
                    "icon": f"https://example.test/{version}/band.png",
                }
            },
            "equipInfo": {
                "equip_shared": {
                    "name": f"{label}装备",
                    "desc": "<color=#fff>攻击</color>+1",
                    "icon": f"https://example.test/{version}/equip.png",
                }
            },
            "chessInfo": {
                "chess_test": {
                    "id": "chess_test",
                    "charId": "char_test",
                    "charName": f"{label}干员",
                    "garrisonIds": ["ability_test"],
                }
            },
            "garrisonInfo": {"ability_test": {"description": f"{label}能力", "eventTypeDesc": "测试能力"}},
            "titleInfo": {
                "comment_1": {"id": "comment_1", "name": f"{label}称号", "picId": "comment_icon_1_0"}
            },
        }

    def record(record_id="recent-one", *, version="v2", **overrides):
        return {
            "id": record_id,
            "activityId": "synthetic-season",
            "versionId": version,
            "completeState": 1,
            "bandId": "band_shared",
            "gameStartTs": 100,
            "gameEndTs": 160,
            "chessSquad": [{"chessId": "chess_test", "equips": [{"equipId": "equip_shared"}]}],
            **overrides,
        }

    def build(*, records=(), favorites=(), career=None, resources=None, player=None, **view_kwargs):
        data = type_validate_python(
            GarrisonData,
            {
                "history": {"records": list(records), "favourRecords": list(favorites)},
                "career": career or {},
                "gameUserInfo": player or {},
            },
        )
        metadata = type_validate_python(
            GarrisonResources, {"resources": resources if resources is not None else [resource()]}
        )
        return GarrisonView.from_data(data, metadata, uid="synthetic-uid", **view_kwargs)

    return build, record, resource


def test_empty_history_has_no_fabricated_records_or_lifetime_counts(garrison_factory):
    build, _, _ = garrison_factory
    view = build()
    assert view.records == []
    assert not view.is_detail
    assert view.activity_id == "synthetic-season"
    assert view.version_id == "v2"
    assert next(metric.value for metric in view.metrics if metric.label == "总模拟数") == "未知"
    assert all(mode.win_percent is None for mode in view.modes)
    assert view.recent_count == 0
    assert view.recent_scope
    assert next(metric.value for metric in view.metrics if metric.label == "游戏时长") == "未知"
    assert view.strategies == []
    assert view.bonds == []
    boss_metric = next(metric for metric in view.metrics if metric.label == "Boss 击杀")
    assert (boss_metric.value, boss_metric.secondary_label, boss_metric.secondary_value) == ("未知", "隐秘", "未知")
    assert boss_metric.detail == view.recent_scope
    assert all(dimension.count is None for dimension in view.title_dimensions)
    assert view.title_scale == 1
    assert not view.title_radar_complete


@pytest.mark.parametrize("index", [0, -1, 2])
@pytest.mark.parametrize("favored", [False, True])
def test_detail_index_never_crosses_history_lists(garrison_factory, index, favored):
    build, record, _ = garrison_factory
    with pytest.raises(ValueError, match="编号超出范围"):
        build(records=[record()], favorites=[record("favorite-only")], record_index=index, favored=favored)


def test_empty_favorites_do_not_fall_back_to_recent(garrison_factory):
    build, record, _ = garrison_factory
    with pytest.raises(ValueError, match="收藏战绩编号超出范围：共 0 条"):
        build(records=[record()], record_index=1, favored=True)


def test_numbering_preserves_each_api_list_and_favorite_identity(garrison_factory):
    build, record, _ = garrison_factory
    recent = [record("z-last-name"), record("a-first-name")]
    favorites = [record("a-first-name"), record("favorite-only")]
    view = build(records=recent, favorites=favorites)
    assert [(item.index, item.record_id, item.is_favored) for item in view.records] == [
        (1, "z-last-name", False),
        (2, "a-first-name", True),
    ]
    detail = build(records=recent, favorites=favorites, favored=True, record_index=1)
    assert [(item.index, item.record_id) for item in detail.records] == [(1, "a-first-name")]


def test_old_records_use_their_own_strategy_equipment_ability_and_title_metadata(garrison_factory):
    build, record, resource = garrison_factory
    historical = resource("v1", label="旧版")
    historical["titleInfo"]["comment_1"]["picId"] = "comment_icon_6_2"
    view = build(
        records=[record(version="v1", title="comment_1")], resources=[resource(), historical], record_index=1
    )
    item = view.records[0]
    assert view.season_name == "旧版"
    assert view.version_id == "v1"
    assert item.strategy.name == "旧版策略"
    assert item.strategy.icon_url == "https://example.test/v1/band.png"
    assert item.operators[0].equipment[0].name == "旧版装备"
    assert item.operators[0].equipment[0].description == "攻击+1"
    assert item.operators[0].abilities[0].description == "旧版能力"
    assert item.title == "旧版称号"
    assert item.title_icon_url == _TITLE_BASE + "comment_icon_6_2.png"
    assert item.started_at == 100
    assert item.ended_at == 160
    assert item.duration_label == "1分0秒"


def test_record_bonds_sort_by_layer_with_stable_ties_and_original_activation(garrison_factory):
    build, record, _ = garrison_factory
    bonds = [
        {"bondId": "low", "layer": 1, "activate": 1},
        {"bondId": "tie-first", "layer": 9, "activate": 0},
        {"bondId": "zero", "layer": 0, "activate": 1},
        {"bondId": "highest", "layer": 25, "activate": 0},
        {"bondId": "tie-second", "layer": 9, "activate": 1},
    ]
    item = record(bondInfo=bonds)
    overview = build(records=[item])
    detail = build(favorites=[item], favored=True, record_index=1)
    expected = [
        ("highest", 25, "未激活"),
        ("tie-first", 9, "未激活"),
        ("tie-second", 9, "已激活"),
        ("low", 1, "已激活"),
        ("zero", 0, "已激活"),
    ]
    assert [(bond.id, bond.count, bond.badge) for bond in overview.records[0].bonds] == expected
    assert detail.records[0].bonds == overview.records[0].bonds


@pytest.mark.parametrize(
    ("start", "end", "duration"),
    [(10, 3671, "1时1分1秒"), (100, 100, "0分0秒"), (0, 100, "未提供"), (200, 100, "未提供")],
)
def test_record_duration_handles_hours_zero_and_missing_or_reversed_times(garrison_factory, start, end, duration):
    build, record, _ = garrison_factory
    view = build(records=[record(gameStartTs=start, gameEndTs=end)])
    assert view.records[0].duration_label == duration


@pytest.mark.parametrize(
    ("hidden", "killed", "label"),
    [
        (False, True, "领袖 · 已击败"),
        (False, False, "领袖 · 未击败"),
        (True, True, "隐秘核心 · 已击败"),
        (True, False, "隐秘核心 · 未击败"),
    ],
)
def test_bosses_keep_historical_identity_and_completion(garrison_factory, hidden, killed, label):
    build, record, resource = garrison_factory
    old = resource("v1")
    old["bossInfo"] = {
        "boss_test": {"enemyId": "enemy_9013_acstmk", "handbookEnemyId": "enemy_9037_aceel"},
        "boss_unknown": {"enemyId": "enemy_future"},
    }
    current = resource()
    current["bossInfo"] = {"boss_test": {"enemyId": "enemy_9035_acspider"}}
    boss_records = [
        {"bossId": "boss_test", "isHidden": hidden, "isKilled": killed},
        {"bossId": "boss_unknown", "isHidden": False, "isKilled": False},
        {"bossId": "boss_missing", "isHidden": True, "isKilled": True},
    ]
    view = build(records=[record(version="v1", acBossInfo=boss_records)], resources=[current, old], record_index=1)
    known, unknown, missing = view.records[0].bosses
    assert (known.is_hidden, known.is_killed) == (hidden, killed)
    assert (known.id, known.name, known.icon_url, known.status_label) == (
        "boss_test",
        "假想敌：鳍",
        "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/main/enemy/enemy_9037_aceel.png",
        label,
    )
    assert (unknown.id, unknown.name, unknown.icon_url, unknown.status_label) == (
        "boss_unknown",
        "enemy_future",
        "",
        "领袖 · 未击败",
    )
    assert (missing.id, missing.name, missing.icon_url, missing.status_label) == (
        "boss_missing",
        "boss_missing",
        "",
        "隐秘核心 · 已击败",
    )

    missing_version = build(records=[record(version="missing", acBossInfo=[boss_records[0]])], record_index=1)
    assert (missing_version.records[0].bosses[0].name, missing_version.records[0].bosses[0].icon_url) == (
        "boss_test",
        "",
    )


def test_missing_historical_metadata_keeps_every_operator_and_raw_item_id(garrison_factory):
    build, record, _ = garrison_factory
    squad = [
        {"chessId": "chess_test", "charId": "char_unknown", "equips": [{"equipId": "equip_shared"}]},
        {"chessId": "only-chess-id"},
        {
            "chessId": "inline-chess",
            "chessInfo": {"charId": "inline-char", "charName": "<b>内联干员</b>", "garrisonIds": ["inline-ability"]},
        },
    ]
    view = build(records=[record(version="missing", title="comment_1", chessSquad=squad)], record_index=1)
    item = view.records[0]
    assert view.version_id == "missing"
    assert view.season_name == "synthetic-season"
    assert item.strategy.name == "band_shared"
    assert item.strategy.icon_url == ""
    assert item.title == "comment_1"
    assert item.title_icon_url == ""
    assert len(item.operators) == 3
    assert {operator.name for operator in item.operators} == {"char_unknown", "only-chess-id", "内联干员"}
    unknown = next(operator for operator in item.operators if operator.char_id == "char_unknown")
    assert unknown.equipment[0].name == "equip_shared"
    assert unknown.equipment[0].icon_url == ""
    inline = next(operator for operator in item.operators if operator.char_id == "inline-char")
    assert inline.abilities[0].name == "inline-ability"


def test_same_version_id_from_another_activity_is_not_used(garrison_factory):
    build, record, resource = garrison_factory
    view = build(
        records=[record(version="v1", title="comment_1")],
        resources=[resource(), resource("v1", activity="another-season")],
    )
    assert view.records[0].strategy.name == "band_shared"
    assert view.records[0].operators[0].equipment[0].name == "equip_shared"
    assert view.records[0].title == "comment_1"
    assert view.records[0].title_icon_url == ""


@pytest.mark.parametrize(("complete", "team", "success"), [(1, 0, True), (0, 1, False)])
def test_cooperative_result_uses_official_complete_state(garrison_factory, complete, team, success):
    build, record, _ = garrison_factory
    view = build(records=[record(modeType="MULTI", completeState=complete, teamComplete=team)])
    assert view.records[0].success is success
    assert view.records[0].result_label == ("模拟完成" if success else "模拟中断")


def test_zero_counters_and_unknown_zero_denominator_are_distinct(garrison_factory):
    build, record, _ = garrison_factory
    career = {
        "medal": {"current": 0, "count": 0},
        "totalSingleBattleCnt": 3,
        "totalSingleBattleWinCnt": 0,
        "totalMultiBattleCnt": 0,
        "totalMultiBattleWinCnt": 0,
        "totalTrophyCnt": 0,
        "totalBeLikeCnt": 0,
        "top1BandUseId": "band_shared",
        "top1BandUseCnt": 0,
        "normalTitles": [{"id": "title_test", "name": "零次称号", "count": 0}],
    }
    view = build(records=[record(trophyBefore=0, trophyAfter=0, coinCost=0)], career=career)
    metrics = {metric.label: metric for metric in view.metrics}
    assert "蚀刻章解锁进度" not in metrics
    assert metrics["游戏时长"].value == "1分"
    assert metrics["游戏时长"].detail == view.recent_scope
    assert metrics["奖杯数量"].value == "0"
    assert metrics["已获赞"].value == "0"
    assert view.modes[0].win_percent == 0
    assert view.modes[0].losses == 3
    assert view.modes[1].win_percent is None
    assert view.strategies[0].count is None
    assert view.strategies[0].recent_count == 1
    assert view.normal_titles[0].count == 0
    assert view.records[0].trophy_change == 0
    assert view.records[0].coin_cost == 0


@pytest.mark.parametrize(
    ("pic_id", "expected_stem"),
    [("comment_icon_6_2", "comment_icon_6_2"), ("", "comment_icon_1_0"), ("comment_icon_7", "")],
)
def test_career_title_icons_prioritize_entries_and_only_fall_back_when_missing(
    garrison_factory, pic_id, expected_stem
):
    build, _, _ = garrison_factory
    view = build(
        career={
            "normalTitles": [{"id": "comment_1", "name": "内联称号", "picId": pic_id, "count": 0}],
            "specialTitles": [{"id": "special", "name": "特殊称号", "picId": "comment_icon_6", "count": 2}],
            "titleCntInfo": {"comment_1": 9},
        }
    )
    assert [(title.name, title.count) for title in view.normal_titles] == [("内联称号", 0)]
    assert [(title.name, title.count) for title in view.special_titles] == [("特殊称号", 2)]
    assert view.other_titles == []
    assert view.normal_titles[0].icon_url == (
        f"{_TITLE_BASE}{expected_stem}.png" if expected_stem else ""
    )
    assert view.special_titles[0].icon_url == _TITLE_BASE + "comment_icon_6.png"


def test_title_count_dictionary_uses_metadata_without_deriving_icons_from_title_ids(garrison_factory):
    build, _, _ = garrison_factory
    view = build(career={"titleCntInfo": {"comment_1": 0, "comment_2": 4}})
    assert view.normal_titles == []
    assert [(title.name, title.count, title.icon_url) for title in view.special_titles] == [
        ("新版称号", 0, _TITLE_BASE + "comment_icon_1_0.png")
    ]
    assert [(title.name, title.count, title.icon_url) for title in view.other_titles] == [("comment_2", 4, "")]


@pytest.mark.parametrize(
    "pic_id",
    ["", "comment_icon_7", "comment_icon_1_3", "../comment_icon_1_0", "comment_icon_1_0.png", "comment_icon_1_0\n"],
)
def test_unknown_title_pic_ids_keep_names_and_counts_without_image_paths(garrison_factory, pic_id):
    build, record, resource = garrison_factory
    metadata = resource()
    metadata["titleInfo"]["comment_1"]["picId"] = pic_id
    view = build(
        records=[record(title="comment_1")], career={"titleCntInfo": {"comment_1": 0}}, resources=[metadata]
    )
    assert view.normal_titles == view.special_titles == []
    assert (view.other_titles[0].name, view.other_titles[0].count, view.other_titles[0].icon_url) == (
        "新版称号", 0, ""
    )
    assert (view.records[0].title, view.records[0].title_icon_url) == ("新版称号", "")


@pytest.mark.parametrize(
    ("difficulty", "label", "image"),
    [
        ("FUNNY", "规程等级1", "img_title_mode_funny.png"),
        ("NORMAL", "规程等级8", "img_title_mode_normal.png"),
        ("HARD", "规程等级14", "img_title_mode_hard.png"),
        ("ABYSS", "规程等级20", "img_title_mode_abyss.png"),
        ("FAST", "极速模拟", "img_title_mode_fast.png"),
        ("TRAINING", "教学模拟", "img_title_mode_training.png"),
        ("FUTURE", "规程等级20", ""),
    ],
)
def test_difficulty_backgrounds_use_api_category_without_inferring_from_level(
    garrison_factory, difficulty, label, image
):
    build, record, _ = garrison_factory
    view = build(
        records=[record(modeDifficulty=difficulty, mode=label)],
        career={"modeDifficulty": difficulty, "mode": label},
    )
    expected = _MODE_BASE + image if image else ""
    best = next(metric for metric in view.metrics if metric.label == "最佳记录")
    assert (best.value, best.background_url) == (label, expected)
    assert (view.records[0].difficulty_label, view.records[0].difficulty_background_url) == (label, expected)


@pytest.mark.parametrize("tier", [0, 1, 6, 7])
def test_operator_tier_icons_do_not_replace_unknown_tiers(garrison_factory, tier):
    build, record, _ = garrison_factory
    view = build(
        records=[record(chessSquad=[{"chessId": "chess_test", "chessInfo": {"chessLevel": tier}}])]
    )
    operator = view.records[0].operators[0]
    assert operator.tier == tier
    assert operator.tier_icon_url == (
        f"{_OUTER_BASE}arts/chesslevelsprite/chess_level_icon_{tier}.png" if 1 <= tier <= 6 else ""
    )


@pytest.mark.parametrize(
    ("char_id", "expected"),
    [
        ("char_1036_fang2", "https://web.hycdn.cn/arknights/game/assets/char/portrait/char_1036_fang2.png"),
        ("char_1037_amiya3", "https://web.hycdn.cn/arknights/game/assets/char/portrait/char_1037_amiya3.png"),
        ("", ""),
    ],
)
def test_operator_half_portraits_use_character_assets_without_inventing_skin_ids(
    garrison_factory, monkeypatch, tmp_path, char_id, expected
):
    from nonebot_plugin_skland import filters

    monkeypatch.setattr(filters, "CACHE_DIR", tmp_path)
    build, record, _ = garrison_factory
    view = build(
        records=[record(version="missing", chessSquad=[{"chessId": "unknown-chess", "charId": char_id}])]
    )
    assert view.records[0].operators[0].half_portrait_url == expected


@pytest.mark.parametrize("complete", [0, 1])
def test_recent_boss_metric_counts_only_kills_with_hidden_as_subset_regardless_of_result(garrison_factory, complete):
    build, record, _ = garrison_factory
    view = build(
        records=[
            record(
                completeState=complete,
                acBossInfo=[
                    {"bossId": "normal-killed", "isHidden": False, "isKilled": True},
                    {"bossId": "hidden-killed", "isHidden": True, "isKilled": True},
                    {"bossId": "normal-alive", "isHidden": False, "isKilled": False},
                    {"bossId": "hidden-alive", "isHidden": True, "isKilled": False},
                ],
            )
        ],
        career={"totalSingleBattleHardWinCnt": 99, "totalMultiBattleHardWinCnt": 88},
    )
    metrics = {metric.label: metric for metric in view.metrics}
    assert "独立高难完成" not in metrics
    assert "联合高难完成" not in metrics
    metric = metrics["Boss 击杀"]
    assert (metric.value, metric.secondary_label, metric.secondary_value) == ("2", "隐秘", "1")
    assert metric.detail == view.recent_scope
    assert metrics["游戏时长"].secondary_label == metrics["游戏时长"].secondary_value == ""


@pytest.mark.parametrize(
    "bosses",
    [
        [],
        [
            {"bossId": "normal-alive", "isHidden": False, "isKilled": False},
            {"bossId": "hidden-alive", "isHidden": True, "isKilled": False},
        ],
    ],
)
def test_recent_boss_metric_preserves_observed_zero_without_inferring_kills_from_success(garrison_factory, bosses):
    build, record, _ = garrison_factory
    view = build(records=[record(completeState=1, acBossInfo=bosses)])
    metric = next(metric for metric in view.metrics if metric.label == "Boss 击杀")
    assert (metric.value, metric.secondary_value) == ("0", "0")
    assert metric.detail == view.recent_scope


def test_common_strategies_rank_recent_five_with_stable_ties_and_actual_badges(garrison_factory):
    build, record, _ = garrison_factory
    observations = [
        ("fifth", 0),
        ("second", 1),
        ("first", 0),
        ("third", 1),
        ("fourth", 1),
        ("sixth", 1),
        ("first", 1),
        ("second", 0),
        ("third", 0),
        ("fourth", 0),
    ]
    view = build(
        records=[
            record(str(index), bandId=band_id, completeState=complete)
            for index, (band_id, complete) in enumerate(observations)
        ],
        career={
            "top1BandUseId": "career-only",
            "top1BandUseCnt": 999,
            "top2BandUseId": "sixth",
            "top2BandUseCnt": 99,
            "top3BandUseId": "first",
            "top3BandUseCnt": 0,
            "bandBadges": [
                {"id": "first", "masterVictor": True},
                {"id": "second", "masterVictor": False},
                {"id": "badge-only", "masterVictor": True},
            ],
            "specialBandIds": ["special-only"],
        },
    )
    assert [item.id for item in view.strategies] == ["second", "first", "third", "fourth", "fifth"]
    assert all(item.count is None for item in view.strategies)
    assert [item.badge_icon_url for item in view.strategies] == [
        _SETTLEMENT_BASE + "title_team_logo_victor.png",
        _SETTLEMENT_BASE + "title_team_logo_master.png",
        "",
        "",
        "",
    ]
    assert [(item.recent_count, item.recent_wins, item.win_percent) for item in view.strategies] == [
        (2, 1, 50),
        (2, 1, 50),
        (2, 1, 50),
        (2, 1, 50),
        (1, 0, 0),
    ]


@pytest.mark.parametrize("has_recent", [False, True])
def test_preferences_never_fill_from_career_badges_or_inactive_records(garrison_factory, has_recent):
    build, record, _ = garrison_factory
    view = build(
        records=[record(bandId="", bondInfo=[{"bondId": "inactive", "activate": 0, "layer": 99}])]
        if has_recent
        else [],
        career={
            "top1BandUseId": "career-first",
            "top1BandUseCnt": 99,
            "top2BandUseId": "career-second",
            "top2BandUseCnt": 88,
            "top3BandUseId": "career-third",
            "top3BandUseCnt": 77,
            "top1ActivateBondId": "inactive",
            "top2ActivateBondId": "unobserved",
            "top3ActivateBondId": "also-unobserved",
            "bandBadges": [{"id": "badge-only", "masterVictor": True}],
            "specialBandIds": ["special-only"],
        },
    )
    assert view.strategies == []
    assert view.bonds == []


def test_preferences_ignore_empty_ids_but_keep_unknown_nonempty_ids(garrison_factory):
    build, record, _ = garrison_factory
    view = build(
        records=[
            record("empty", bandId="", bondInfo=[{"bondId": "", "activate": 1, "layer": 99}]),
            record("blank", bandId="   ", bondInfo=[{"bondId": "   ", "activate": 1, "layer": 99}]),
            record(
                "unknown",
                bandId="future-band",
                completeState=0,
                bondInfo=[{"bondId": "future-bond", "activate": 1, "layer": 0}],
            ),
        ]
    )
    assert [(item.id, item.name, item.icon_url, item.count, item.recent_count) for item in view.strategies] == [
        ("future-band", "future-band", "", None, 1)
    ]
    assert [(item.id, item.name, item.icon_url, item.count, item.recent_count, item.max_layer) for item in view.bonds] == [
        ("future-bond", "future-bond", "", None, 1, 0)
    ]


def test_common_bonds_rank_recent_five_across_all_types_with_stable_ties(garrison_factory):
    build, record, resource = garrison_factory
    bond_ids = ["fifth", "second", "first", "third", "fourth", "sixth"]
    metadata = resource()
    metadata["bondInfo"] = {
        bond_id: {"name": f"盟约{bond_id}", "type": bond_type}
        for bond_id, bond_type in zip(bond_ids, ["REGULAR", "SEASON", "FUTURE", "", "REGULAR", "SEASON"])
    }
    view = build(
        records=[
            record(
                "first",
                bondInfo=[
                    {"bondId": bond_id, "layer": layer, "activate": 1}
                    for bond_id, layer in zip(bond_ids, [999, 2, 3, 4, 5, 6])
                ],
            ),
            record(
                "second",
                bondInfo=[
                    {"bondId": bond_id, "layer": 0, "activate": 1}
                    for bond_id in ["first", "second", "third", "fourth"]
                ],
            ),
            record("third", bondInfo=[{"bondId": "second", "layer": 1, "activate": 1}]),
        ],
        resources=[metadata],
        career={"top1ActivateBondId": "sixth", "top2ActivateBondId": "career-only"},
    )
    assert [(item.id, item.recent_count, item.max_layer) for item in view.bonds] == [
        ("second", 3, 2),
        ("first", 2, 3),
        ("third", 2, 4),
        ("fourth", 2, 5),
        ("fifth", 1, 999),
    ]
    assert all(item.count is None for item in view.bonds)


@pytest.mark.parametrize("complete", [0, 1])
@pytest.mark.parametrize("master", [None, False, True])
def test_record_strategy_badges_use_career_state_not_record_outcome(garrison_factory, complete, master):
    build, record, _ = garrison_factory
    career = {"bandBadges": [] if master is None else [{"id": "band_shared", "masterVictor": master}]}
    view = build(records=[record(completeState=complete)], career=career)
    expected = "" if master is None else f"{_SETTLEMENT_BASE}title_team_logo_{'master' if master else 'victor'}.png"
    assert view.records[0].strategy.badge_icon_url == expected
    other = build(records=[record(activityId="other-season", completeState=complete)], career=career)
    assert other.records[0].strategy.badge_icon_url == ""


@pytest.mark.parametrize(
    ("count", "level"),
    [(0, 1), (9, 1), (10, 2), (29, 2), (30, 3), (60, 4), (100, 5), (150, 6), (200, 7), (257, 7), (299, 7), (300, 8)],
)
def test_trophy_badge_uses_post_record_total_and_official_thresholds(garrison_factory, count, level):
    build, record, _ = garrison_factory
    view = build(records=[record(trophyBefore=300, trophyAfter=count)], career={"totalTrophyCnt": 900})
    item = view.records[0]
    assert (item.trophy_after, item.trophy_change) == (count, count - 300)
    assert item.trophy_icon_url == f"{_OUTER_BASE}arts/medalicon/trophy_level{level}_icon.png"


def test_lifetime_statistics_do_not_depend_on_selected_list_or_detail(garrison_factory):
    build, record, _ = garrison_factory
    career = {
        "totalSingleBattleCnt": 80,
        "totalSingleBattleWinCnt": 60,
        "totalMultiBattleCnt": 20,
        "totalMultiBattleWinCnt": 5,
    }
    kwargs = {"records": [record()], "favorites": [record("favorite-a"), record("favorite-b")], "career": career}
    overview = build(**kwargs)
    favorite = build(**kwargs, favored=True)
    detail = build(**kwargs, favored=True, record_index=2)
    assert overview.metrics == favorite.metrics == detail.metrics
    assert overview.modes == favorite.modes == detail.modes
    assert next(metric.value for metric in detail.metrics if metric.label == "总模拟数") == "100"
    assert [mode.win_percent for mode in detail.modes] == [75, 25]


def test_player_names_and_official_descriptions_are_plain_text(garrison_factory):
    build, record, resource = garrison_factory
    metadata = resource()
    metadata["bandInfo"]["band_shared"]["desc"] = "【能力】\\n<@ba.vup>提升</> <color=#fff>1</color> <预备干员>"
    view = build(
        records=[record(events=["<b>事件</b>"])], resources=[metadata], player={"name": "<span>测试博士</span>"}
    )
    assert view.nickname == "测试博士"
    assert view.records[0].strategy.description == "【能力】\n提升 1 预备干员"
    assert view.records[0].events == ["事件"]
    assert view.avatar_url == ""


@pytest.mark.parametrize("resources", [[], [{"versionInfo": {"versionId": "v1"}}]])
def test_current_activity_requires_valid_first_resource(app, resources):
    from nonebot.compat import type_validate_python

    from nonebot_plugin_skland.schemas.arknights.garrison import GarrisonResources

    metadata = type_validate_python(GarrisonResources, {"resources": resources})
    with pytest.raises(ValueError, match="有效的当前活动"):
        _ = metadata.current_activity_id


def test_recent_statistics_ignore_foreign_activity_favorites_and_selected_detail(garrison_factory):
    build, record, _ = garrison_factory
    win = record(
        "win",
        bondInfo=[{"bondId": "observed", "layer": 2, "activate": 1}],
        acBossInfo=[
            {"bossId": "normal", "isKilled": True},
            {"bossId": "hidden-alive", "isHidden": True, "isKilled": False},
        ],
    )
    kwargs = {
        "records": [
            record(
                "win",
                activityId="another-season",
                gameStartTs=0,
                bandId="foreign-band",
                bondInfo=[{"bondId": "foreign-bond", "layer": 999, "activate": 1}],
                acBossInfo=[{"bossId": "foreign-boss", "isHidden": True, "isKilled": True}],
            ),
            win,
            win,
            record(
                "loss",
                version="older-version",
                completeState=0,
                teamComplete=1,
                gameEndTs=220,
                bondInfo=[{"bondId": "observed", "layer": 3, "activate": 1}],
                acBossInfo=[{"bossId": "hidden-killed", "isHidden": True, "isKilled": True}],
            ),
        ],
        "favorites": [
            record(
                "favorite-only",
                activityId="another-season",
                bandId="favorite-band",
                acBossInfo=[{"bossId": "favorite-boss", "isHidden": True, "isKilled": True}],
                gameStartTs=0,
                bondInfo=[{"bondId": "observed", "layer": 99, "activate": 1}],
            ),
            record("favorite-current", gameStartTs=0),
        ],
        "career": {
            "totalSingleBattleCnt": 80,
            "totalSingleBattleWinCnt": 60,
            "totalMultiBattleCnt": 20,
            "totalMultiBattleWinCnt": 5,
            "top1BandUseId": "band_shared",
            "top1BandUseCnt": 26,
            "top1ActivateBondId": "observed",
        },
    }
    overview = build(**kwargs)
    views = [
        overview,
        build(**kwargs, record_index=1),
        build(**kwargs, favored=True),
        build(**kwargs, favored=True, record_index=1),
    ]
    for view in views:
        assert view.recent_count == 2
        assert view.recent_scope == overview.recent_scope
        assert view.metrics == overview.metrics
        assert view.modes == overview.modes
        assert view.strategies == overview.strategies
        assert view.bonds == overview.bonds
        strategy = view.strategies[0]
        assert (strategy.count, strategy.recent_count, strategy.recent_wins, strategy.win_percent) == (None, 2, 1, 50)
        assert (view.bonds[0].count, view.bonds[0].recent_count, view.bonds[0].max_layer) == (None, 2, 3)
        metrics = {metric.label: metric for metric in view.metrics}
        assert metrics["总模拟数"].value == "100"
        assert metrics["游戏时长"].value == "3分"
        assert metrics["游戏时长"].detail == view.recent_scope
        assert (metrics["Boss 击杀"].value, metrics["Boss 击杀"].secondary_value) == ("2", "1")
        assert metrics["Boss 击杀"].detail == view.recent_scope
    assert views[-1].activity_id == "another-season"


def test_requested_activity_defines_recent_sample_not_latest_resource(garrison_factory):
    build, record, resource = garrison_factory
    view = build(
        records=[
            record("latest", gameStartTs=0),
            record("requested", activityId="requested-season", version="v1", completeState=0),
        ],
        resources=[resource(), resource("v1", activity="requested-season")],
        activity_id="requested-season",
        career={"top1BandUseId": "band_shared", "top1BandUseCnt": 0, "top2BandUseId": "unobserved"},
    )
    assert view.recent_count == 1
    assert [(item.count, item.recent_count, item.recent_wins, item.win_percent) for item in view.strategies] == [
        (None, 1, 0, 0)
    ]
    assert next(metric.value for metric in view.metrics if metric.label == "游戏时长") == "1分"


def test_recent_bonds_deduplicate_activation_and_keep_zero_without_changing_record_layers(garrison_factory):
    build, record, _ = garrison_factory
    view = build(
        records=[
            record(
                "first",
                bondInfo=[
                    {"bondId": "zero", "layer": 0, "activate": 1},
                    {"bondId": "layered", "layer": 2, "activate": 1},
                    {"bondId": "layered", "layer": 5, "activate": 1},
                    {"bondId": "layered", "layer": 99, "activate": 0},
                    {"bondId": "inactive", "layer": 99, "activate": 0},
                ],
            ),
            record(
                "second",
                bondInfo=[
                    {"bondId": "zero", "layer": 9, "activate": 0},
                    {"bondId": "layered", "layer": 6, "activate": 1},
                    {"bondId": "layered", "layer": 4, "activate": 1},
                ],
            ),
        ],
        career={"top1ActivateBondId": "zero", "top2ActivateBondId": "layered", "top3ActivateBondId": "inactive"},
    )
    assert [(item.id, item.count, item.recent_count, item.max_layer) for item in view.bonds] == [
        ("layered", None, 2, 6),
        ("zero", None, 1, 0),
    ]
    assert [(item.id, item.count, item.badge) for item in view.records[0].bonds] == [
        ("layered", 99, "未激活"),
        ("inactive", 99, "未激活"),
        ("layered", 5, "已激活"),
        ("layered", 2, "已激活"),
        ("zero", 0, "已激活"),
    ]


def test_four_unlayered_bonds_keep_zero_in_records_and_preferences(garrison_factory):
    build, record, resource = garrison_factory
    bond_ids = ["emptyShip", "maniShip", "soloShip", "suntShip"]
    metadata = resource()
    metadata["bondInfo"] = {bond_id: {"name": bond_id, "activeCount": 0} for bond_id in bond_ids}
    view = build(
        records=[record(bondInfo=[{"bondId": bond_id, "layer": 0, "activate": 1} for bond_id in bond_ids])],
        resources=[metadata],
    )
    assert [(item.id, item.count) for item in view.records[0].bonds] == [(bond_id, 0) for bond_id in bond_ids]
    assert [(item.id, item.count, item.recent_count, item.max_layer) for item in view.bonds] == [
        (bond_id, None, 1, 0) for bond_id in bond_ids
    ]


@pytest.mark.parametrize(
    ("durations", "expected"),
    [([0], "0分"), ([59], "0分"), ([30, 30], "1分"), ([4321], "1时12分"), ([321179], "89时12分")],
)
def test_recent_duration_sums_seconds_before_truncating_to_minutes(garrison_factory, durations, expected):
    build, record, _ = garrison_factory
    view = build(
        records=[record(str(index), gameEndTs=100 + duration) for index, duration in enumerate(durations)]
    )
    metric = next(metric for metric in view.metrics if metric.label == "游戏时长")
    assert metric.value == expected
    assert metric.detail == view.recent_scope
    assert view.recent_count == len(durations)


@pytest.mark.parametrize(
    "timestamps",
    [
        {},
        {"gameStartTs": 100},
        {"gameEndTs": 160},
        {"gameStartTs": 0, "gameEndTs": 160},
        {"gameStartTs": -1, "gameEndTs": 160},
        {"gameStartTs": 200, "gameEndTs": 100},
    ],
)
@pytest.mark.parametrize("invalid_first", [False, True])
def test_incomplete_recent_duration_never_displays_partial_total(garrison_factory, timestamps, invalid_first):
    build, record, _ = garrison_factory
    invalid = record("invalid")
    invalid.pop("gameStartTs")
    invalid.pop("gameEndTs")
    invalid.update(timestamps)
    records = [invalid, record("valid")] if invalid_first else [record("valid"), invalid]
    view = build(records=records)
    assert view.recent_count == 2
    assert next(metric.value for metric in view.metrics if metric.label == "游戏时长") == "未知"


def test_title_count_dictionary_classifies_verified_icons_and_preserves_other_titles(garrison_factory):
    build, _, resource = garrison_factory
    metadata = resource()
    metadata["titleInfo"] = {
        "normal-first": {"picId": "comment_icon_1_1"},
        "normal-second": {"picId": "comment_icon_6_2"},
        "special": {"picId": "comment_icon_3_0"},
        "unclassified": {"picId": "comment_icon_4"},
        "new-format": {"picId": "comment_icon_7_0", "name": "<b>新称号</b>"},
        "illegal": {"picId": "../comment_icon_2_0"},
    }
    view = build(
        resources=[metadata],
        career={
            "titleCntInfo": {
                "normal-first": 0,
                "normal-second": 2,
                "special": 3,
                "unclassified": 4,
                "new-format": 5,
                "illegal": 6,
                "unknown": 7,
            }
        },
    )
    assert [(item.id, item.count) for item in view.normal_titles] == [("normal-first", 0), ("normal-second", 2)]
    assert [(item.id, item.count) for item in view.special_titles] == [("special", 3)]
    assert [(item.id, item.name, item.count, item.icon_url) for item in view.other_titles] == [
        ("unclassified", "unclassified", 4, _TITLE_BASE + "comment_icon_4.png"),
        ("new-format", "新称号", 5, ""),
        ("illegal", "illegal", 6, ""),
        ("unknown", "unknown", 7, ""),
    ]


def test_title_api_categories_win_over_icon_category_and_duplicate_counts(garrison_factory):
    build, _, _ = garrison_factory
    view = build(
        career={
            "normalTitles": [{"id": "comment_1", "name": "<b>内联称号</b>", "type": "<b>标记</b>"}],
            "specialTitles": [
                {"id": "comment_1", "name": "重复称号", "count": 99},
                {"id": "special", "picId": "comment_icon_2_2", "count": 0},
            ],
            "titleCntInfo": {"comment_1": 0, "special": 9},
        }
    )
    assert [(item.id, item.name, item.count, item.badge) for item in view.normal_titles] == [
        ("comment_1", "内联称号", 0, "标记")
    ]
    assert view.normal_titles[0].icon_url == _TITLE_BASE + "comment_icon_1_0.png"
    assert [(item.id, item.count) for item in view.special_titles] == [("special", 0)]
    assert view.special_titles[0].icon_url == _TITLE_BASE + "comment_icon_2_2.png"
    assert view.other_titles == []


@pytest.mark.parametrize(
    ("counts", "scale", "complete"),
    [
        ({}, 1, False),
        ({"COIN": 0, "KILL": 7, "UNKNOWN": 999}, 7, False),
        ({"COIN": 0, "KILL": 0, "DAMAGE": 0, "BOND": 0, "CHAR": 0, "EQUIP": 0}, 1, True),
        ({"EQUIP": 6, "CHAR": 5, "BOND": 4, "DAMAGE": 3, "KILL": 2, "COIN": 1}, 6, True),
    ],
)
def test_title_dimensions_use_only_career_counts_with_fixed_order_and_unknowns(garrison_factory, counts, scale, complete):
    build, record, _ = garrison_factory
    view = build(
        records=[record(title="comment_1")],
        favorites=[record("favorite", title="comment_1")],
        career={"titleTypeCnt": counts, "titleCntInfo": {"comment_1": 200}},
    )
    keys = ["COIN", "KILL", "DAMAGE", "BOND", "CHAR", "EQUIP"]
    assert [item.key for item in view.title_dimensions] == keys
    assert [item.count for item in view.title_dimensions] == [counts.get(key) for key in keys]
    assert [item.icon_url for item in view.title_dimensions] == [
        f"{_TITLE_BASE}comment_icon_{index}.png" for index in [4, 2, 6, 1, 5, 3]
    ]
    assert [item.label for item in view.title_dimensions] == [
        "资金管理", "补救能力", "领袖挑战", "盟约理解", "人力调度", "装备活用"
    ]
    assert view.title_scale == scale
    assert view.title_radar_complete is complete
