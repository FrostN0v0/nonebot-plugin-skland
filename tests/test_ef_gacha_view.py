import pytest


def _pull(seq_id, rarity, item_id, *, is_free=False, is_new=False, pool_version=None):
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfGachaPull

    return EfGachaPull(
        pool_name="Test pool",
        item_id=item_id,
        item_name=item_id,
        item_type="char",
        rarity=rarity,
        is_new=is_new,
        is_free=is_free,
        seq_id=seq_id,
        pool_version=pool_version,
    )


def _pool(pool_id, groups, *, up_six_chars=()):
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfGachaGroup
    from nonebot_plugin_skland.schemas.endfield.gacha.pool import EfGachaPoolInfo

    return EfGachaPoolInfo(
        pool_id=pool_id,
        pool_name=pool_id,
        pool_type="weapon" if pool_id.startswith(("weapon", "rerun_wpn_")) else "char",
        records=[EfGachaGroup(gacha_ts=timestamp, pulls=pulls) for timestamp, pulls in groups],
        up_six_chars=list(up_six_chars),
    )


def _view(record, **kwargs):
    from nonebot_plugin_skland.schemas.endfield.gacha.view import EfGachaView

    return EfGachaView.from_record(record, nickname="Test", role_id="123", server_name="国服", **kwargs)


def _pool_views(view):
    return [pool for category in view.categories for pool in category.pools]


def _five_counts(five_stars):
    return [(five.item_id, five.count) for five in five_stars]


def test_paid_intervals_span_groups_without_free_pulls_consuming_pity_or_fives(app):
    from nonebot_plugin_skland.schemas.endfield.gacha.statistics import EfGroupedGachaRecord

    pool = _pool(
        "special_history",
        [
            (100, [_pull(1, 6, "old_six")]),
            (200, [_pull(2, 5, "five_b"), _pull(3, 4, "four")]),
            (
                300,
                [
                    _pull(4, 6, "free_six", is_free=True),
                    _pull(5, 5, "free_five", is_free=True),
                    _pull(6, 5, "free_five", is_free=True),
                ],
            ),
            (400, [_pull(7, 5, "five_b"), _pull(8, 5, "five_a")]),
            (500, [_pull(9, 6, "up_six", is_new=True), _pull(10, 5, "pending_five")]),
            (600, [_pull(11, 5, "free_tail", is_free=True)]),
        ],
        up_six_chars=["up_six"],
    )
    view = _view(EfGroupedGachaRecord(special_pools=[pool]))
    events = _pool_views(view)[0].periods[0].events

    assert [(event.gacha_ts, event.is_free) for event in events] == [
        (600, True),
        (500, False),
        (300, True),
        (100, False),
    ]
    assert events[0].six_stars == []
    assert _five_counts(events[0].five_stars) == [("free_tail", 1)]
    paid_six = events[1].six_stars[0]
    assert paid_six.pity_count == 5
    assert _five_counts(paid_six.five_stars) == [("five_a", 1), ("five_b", 2)]
    assert paid_six.is_up
    assert paid_six.is_new
    assert not paid_six.is_spook
    assert events[1].five_stars == []
    assert events[1].pull_count == 2
    free_six = events[2].six_stars[0]
    assert free_six.pity_count is None
    assert free_six.five_stars == []
    assert free_six.is_spook
    assert not free_six.is_up
    assert _five_counts(events[2].five_stars) == [("free_five", 2)]
    assert events[2].pull_count == 3
    assert events[3].six_stars[0].pity_count == 1
    assert events[3].six_stars[0].five_stars == []
    assert _pool_views(view)[0].pool.pity_count == 1


def test_multi_six_batches_are_atomic_and_newest_first_with_distinct_free_event(app):
    from nonebot_plugin_skland.schemas.endfield.gacha.statistics import EfGroupedGachaRecord

    pool = _pool(
        "joint_history",
        [
            (100, [_pull(1, 5, "before_batch")]),
            (
                200,
                [
                    _pull(2, 6, "paid_first"),
                    _pull(3, 5, "between_sixes"),
                    _pull(4, 6, "free_first", is_free=True),
                    _pull(5, 6, "free_last", is_free=True),
                    _pull(6, 6, "paid_last"),
                    _pull(7, 4, "after_sixes"),
                ],
            ),
            (300, [_pull(8, 6, "next_batch")]),
        ],
        up_six_chars=["paid_first"],
    )
    view = _view(EfGroupedGachaRecord(joint_pools=[pool]))
    events = _pool_views(view)[0].periods[0].events

    assert [event.key for event in events] == [
        "joint_history:all:300:paid",
        "joint_history:all:200:paid",
        "joint_history:all:200:free",
    ]
    assert events[0].six_stars[0].pity_count == 2
    assert events[0].six_stars[0].five_stars == []
    paid = events[1]
    assert paid.pull_count == 4
    assert [(six.item_id, six.pity_count) for six in paid.six_stars] == [("paid_last", 2), ("paid_first", 2)]
    assert [_five_counts(six.five_stars) for six in paid.six_stars] == [
        [("between_sixes", 1)],
        [("before_batch", 1)],
    ]
    assert not paid.six_stars[0].is_spook
    assert paid.six_stars[1].is_up
    free = events[2]
    assert free.pull_count == 2
    assert [(six.item_id, six.pity_count) for six in free.six_stars] == [("free_last", None), ("free_first", None)]


def test_category_slices_keep_full_totals_and_pool_local_intervals_including_empty_selection(app):
    from nonebot_plugin_skland.schemas.endfield.gacha.statistics import EfGroupedGachaRecord

    record = EfGroupedGachaRecord(
        special_pools=[
            _pool("special_old", [(100, [_pull(1, 4, "old_four")])], up_six_chars=["up"]),
            _pool("special_new", [(900, [_pull(4, 6, "up")])], up_six_chars=["up"]),
            _pool("special_middle", [(500, [_pull(2, 4, "four"), _pull(3, 6, "up")])], up_six_chars=["up"]),
        ],
        rerun_pools=[
            _pool("rerun_chr_old", [(250, [_pull(5, 4, "rerun_four")])], up_six_chars=["rerun_up"]),
            _pool("rerun_chr_new", [(850, [_pull(6, 6, "rerun_up")])], up_six_chars=["rerun_up"]),
        ],
        weapon_pools=[
            _pool("weapon_old", [(400, [_pull(1, 6, "weapon")])]),
            _pool("weapon_new", [(800, [_pull(2, 6, "weapon")])]),
        ],
        joint_pools=[
            _pool("joint_old", [(300, [_pull(1, 6, "joint")])]),
            _pool("joint_new", [(700, [_pull(2, 6, "joint")])]),
        ],
        standard_pools=[_pool("standard", [(600, [_pull(1, 6, "standard")])])],
        beginner_pools=[_pool("beginner", [(200, [_pull(1, 6, "beginner")])])],
    )
    selected = _view(record, begin=1, limit=2)
    assert [category.key for category in selected.categories] == [
        "special",
        "rerun",
        "weapon",
        "joint",
        "standard",
        "beginner",
    ]
    assert [category.total_pulls for category in selected.categories] == [4, 2, 2, 2, 1, 1]

    assert [pool.pool.pool_id for pool in _pool_views(selected)] == [
        "special_middle",
        "rerun_chr_old",
        "weapon_old",
        "joint_old",
    ]
    assert _pool_views(selected)[0].periods[0].events[0].six_stars[0].pity_count == 2
    assert selected.record.total_pulls == 12
    assert selected.record.char_total_pulls == 10
    assert selected.record.weapon_total_pulls == 2
    assert selected.record.special_total_pulls == 4
    assert selected.record.rerun_total_pulls == 2
    assert selected.record.rerun_up_avg == 2.0
    assert selected.record.special_up_avg == 2.0
    assert [pool.pool.pool_id for pool in _pool_views(_view(record, limit=1))] == [
        "special_new",
        "rerun_chr_new",
        "weapon_new",
        "joint_new",
        "standard",
        "beginner",
    ]
    for begin, limit in [(0, 0), (2, 1), (10, None)]:
        empty = _view(record, begin=begin, limit=limit)
        assert _pool_views(empty) == []
        assert empty.record.total_pulls == 12
        assert empty.record.special_up_avg == 2.0


@pytest.mark.parametrize("category", ["special", "rerun", "weapon"])
@pytest.mark.parametrize("unknown_pool_rarity", [4, 6])
def test_missing_up_metadata_makes_category_spook_and_up_average_unknown(app, category, unknown_pool_rarity):
    from nonebot_plugin_skland.schemas.endfield.gacha.statistics import EfGroupedGachaRecord

    prefix = "rerun_chr" if category == "rerun" else category
    unknown_pool = _pool(f"{prefix}_unknown", [(100, [_pull(1, unknown_pool_rarity, "unknown")])])
    known_pool = _pool(
        f"{prefix}_known",
        [(200, [_pull(2, 6, "off")]), (300, [_pull(3, 6, "up")])],
        up_six_chars=["up"],
    )
    record = EfGroupedGachaRecord(**{f"{category}_pools": [unknown_pool, known_pool]})

    assert unknown_pool.total_six_spook is None
    assert not unknown_pool.show_spook_stats
    assert known_pool.total_six_spook == 1
    assert known_pool.show_spook_stats
    assert getattr(record, f"{category}_total_spook") is None
    assert getattr(record, f"{category}_up_avg") is None
    selected = _view(record, limit=1)
    assert [pool.pool.pool_id for pool in _pool_views(selected)] == [known_pool.pool_id]
    assert getattr(selected.record, f"{category}_total_spook") is None
    assert getattr(selected.record, f"{category}_up_avg") is None
    assert selected.categories[0].spook_count is None
    assert selected.categories[0].average is None


@pytest.mark.parametrize(
    ("category", "average"),
    [
        ("special", "special_up_avg"),
        ("rerun", "rerun_up_avg"),
        ("weapon", "weapon_up_avg"),
        ("standard", "standard_six_avg"),
        ("joint", "joint_six_avg"),
    ],
)
def test_paid_average_excludes_free_six_stars_and_paid_tail(app, category, average):
    from nonebot_plugin_skland.schemas.endfield.gacha.statistics import EfGroupedGachaRecord

    pool = _pool(
        "rerun_chr_history" if category == "rerun" else category,
        [
            (100, [_pull(1, 4, "four")]),
            (200, [_pull(2, 6, "up")]),
            (300, [_pull(3, 4, "four")]),
            (400, [_pull(4, 6, "up", is_free=True)]),
            (500, [_pull(5, 4, "four")]),
        ],
        up_six_chars=["up"],
    )
    record = EfGroupedGachaRecord(**{f"{category}_pools": [pool]})

    assert pool.total_six_stars == 2
    assert pool.paid_six_stars == 1
    assert pool.paid_pulls == 4
    assert pool.pity_count == 2
    assert getattr(record, average) == 2.0


@pytest.mark.parametrize(
    ("category", "average"),
    [
        ("special", "special_up_avg"),
        ("rerun", "rerun_up_avg"),
        ("weapon", "weapon_up_avg"),
        ("standard", "standard_six_avg"),
        ("joint", "joint_six_avg"),
    ],
)
def test_paid_average_is_unknown_when_all_six_stars_are_free(app, category, average):
    from nonebot_plugin_skland.schemas.endfield.gacha.statistics import EfGroupedGachaRecord

    pool = _pool(
        "rerun_chr_history" if category == "rerun" else category,
        [
            (100, [_pull(1, 4, "four")]),
            (200, [_pull(2, 6, "up", is_free=True)]),
            (300, [_pull(3, 4, "four")]),
        ],
        up_six_chars=["up"],
    )
    record = EfGroupedGachaRecord(**{f"{category}_pools": [pool]})

    assert pool.total_six_stars == 1
    assert pool.paid_six_stars == 0
    assert getattr(record, average) is None


@pytest.mark.parametrize("category", ["special", "rerun", "weapon"])
def test_up_average_is_unknown_with_only_free_up_despite_paid_off_banner_six(app, category):
    from nonebot_plugin_skland.schemas.endfield.gacha.statistics import EfGroupedGachaRecord

    pool = _pool(
        "rerun_chr_history" if category == "rerun" else category,
        [(100, [_pull(1, 6, "off")]), (200, [_pull(2, 6, "up", is_free=True)])],
        up_six_chars=["up"],
    )
    record = EfGroupedGachaRecord(**{f"{category}_pools": [pool]})

    assert pool.paid_six_stars == 1
    assert getattr(record, f"{category}_total_spook") == 1
    assert getattr(record, f"{category}_up_avg") is None


def test_empty_categories_have_unknown_averages(app):
    from nonebot_plugin_skland.schemas.endfield.gacha.statistics import EfGroupedGachaRecord

    record = EfGroupedGachaRecord()

    assert record.special_up_avg is None
    assert record.rerun_up_avg is None
    assert record.weapon_up_avg is None
    assert record.standard_six_avg is None
    assert record.joint_six_avg is None
    assert record.special_total_spook == 0
    assert record.rerun_total_spook == 0
    assert record.weapon_total_spook == 0
    assert _view(record).categories == []


def test_weapon_categories_slice_independently_without_changing_full_statistics(app):
    from nonebot_plugin_skland.schemas.endfield.gacha.statistics import EfGroupedGachaRecord

    def weapon_pool(pool_id, timestamp, *, six_position=None, version=None):
        return _pool(
            pool_id,
            [
                (
                    timestamp,
                    [
                        _pull(
                            index + 1,
                            6 if index == six_position else 4,
                            "up" if index == six_position else "four",
                            pool_version=version,
                        )
                        for index in range(10)
                    ],
                )
            ],
            up_six_chars=["up"],
        )

    record = EfGroupedGachaRecord(
        weapon_pools=[
            weapon_pool("weapon_old", 100, six_position=9),
            weapon_pool("rerun_wpn_old", 200, six_position=4, version=1),
            weapon_pool("weapon_new", 300),
            weapon_pool("rerun_wpn_new", 400, version=2),
        ]
    )
    full = _view(record)
    selected = _view(record, begin=1, limit=2)

    assert [category.key for category in selected.categories] == ["weapon", "rerun_weapon"]
    assert [[pool.pool.pool_id for pool in category.pools] for category in selected.categories] == [
        ["weapon_old"],
        ["rerun_wpn_old"],
    ]
    assert [category.average for category in selected.categories] == [10.0, 5.0]
    for complete, category in zip(full.categories, selected.categories, strict=True):
        assert category.model_dump(exclude={"pools"}) == complete.model_dump(exclude={"pools"})
        assert category.total_pulls == category.paid_pulls == 20
        assert category.free_pulls == 0
        assert category.six_count == 1
        assert category.spook_count == 0
        assert category.pity_count is None
    assert selected.categories[0].pools[0].periods[0].pity_limit == 80
    assert selected.categories[1].pools[0].periods[0].pity_limit == 4
    assert selected.categories[1].pools[0].six_star_limit == 40
    assert selected.record.weapon_total_pulls == 40
    assert selected.record.weapon_arsenal_quota_consumed == 4 * 1980
    empty = _view(record, begin=5)
    assert len(empty.categories) == 2
    assert all(not category.pools and category.total_pulls == 20 for category in empty.categories)
