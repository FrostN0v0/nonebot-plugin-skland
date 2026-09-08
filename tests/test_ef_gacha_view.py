def _pull(seq_id, rarity, item_id, *, is_free=False, is_new=False):
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
    )


def _pool(pool_id, groups, *, up_six_chars=()):
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfGachaGroup
    from nonebot_plugin_skland.schemas.endfield.gacha.pool import EfGachaPoolInfo

    return EfGachaPoolInfo(
        pool_id=pool_id,
        pool_name=pool_id,
        pool_type="weapon" if pool_id.startswith("weapon") else "char",
        records=[EfGachaGroup(gacha_ts=timestamp, pulls=pulls) for timestamp, pulls in groups],
        up_six_chars=list(up_six_chars),
    )


def _view(record, **kwargs):
    from nonebot_plugin_skland.schemas.endfield.gacha.view import EfGachaView

    return EfGachaView.from_record(record, nickname="Test", role_id="123", server_name="国服", **kwargs)


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
    events = view.pools[0].events

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
    assert view.pools[0].pool.pity_count == 1


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
    events = view.pools[0].events

    assert [event.key for event in events] == [
        "joint_history:300:paid",
        "joint_history:200:paid",
        "joint_history:200:free",
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
            _pool("special_old", [(100, [_pull(1, 4, "old_four")])]),
            _pool("special_new", [(900, [_pull(4, 6, "up")])], up_six_chars=["up"]),
            _pool("special_middle", [(500, [_pull(2, 4, "four"), _pull(3, 6, "up")])], up_six_chars=["up"]),
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

    assert [pool.pool.pool_id for pool in selected.pools] == ["special_middle", "weapon_old", "joint_old"]
    assert selected.pools[0].events[0].six_stars[0].pity_count == 2
    assert selected.record.total_pulls == 10
    assert selected.record.char_total_pulls == 8
    assert selected.record.weapon_total_pulls == 2
    assert selected.record.special_total_pulls == 4
    assert selected.record.special_up_avg == 2.0
    assert [pool.pool.pool_id for pool in _view(record, limit=1).pools] == [
        "special_new",
        "weapon_new",
        "joint_new",
        "standard",
        "beginner",
    ]
    for begin, limit in [(0, 0), (2, 1), (10, None)]:
        empty = _view(record, begin=begin, limit=limit)
        assert empty.pools == []
        assert empty.record.total_pulls == 10
        assert empty.record.special_up_avg == 2.0
