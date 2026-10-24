import pytest


def _pull(seq_id, *, rarity=4, item_id="four", item_type="char", pool_version=1, is_free=False):
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfGachaPull

    return EfGachaPull(
        pool_name="Test pool",
        item_id=item_id,
        item_name=item_id,
        item_type=item_type,
        rarity=rarity,
        is_new=False,
        is_free=is_free,
        seq_id=seq_id,
        pool_version=pool_version,
    )


def _pool(pool_id, groups, *, pool_type="char", up_six_chars=("up",)):
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfGachaGroup
    from nonebot_plugin_skland.schemas.endfield.gacha.pool import EfGachaPoolInfo

    return EfGachaPoolInfo(
        pool_id=pool_id,
        pool_name=pool_id,
        pool_type=pool_type,
        records=[EfGachaGroup(gacha_ts=timestamp, pulls=pulls) for timestamp, pulls in groups],
        up_six_chars=list(up_six_chars),
    )


def _view(*, rerun_pools=(), weapon_pools=(), special_pools=()):
    from nonebot_plugin_skland.schemas.endfield.gacha.view import EfGachaView
    from nonebot_plugin_skland.schemas.endfield.gacha.statistics import EfGroupedGachaRecord

    return EfGachaView.from_record(
        EfGroupedGachaRecord(
            rerun_pools=list(rerun_pools),
            weapon_pools=list(weapon_pools),
            special_pools=list(special_pools),
        ),
        nickname="Test",
        role_id="123",
        server_name="国服",
    )


def _pool_views(view):
    return [pool for category in view.categories for pool in category.pools]


def _weapon_pool(versions, *, sixes=None, pool_id="rerun_wpn_test", up_six_chars=("up",)):
    sixes = sixes or {}
    groups = []
    for claim, version in enumerate(versions):
        claim_sixes = sixes.get(claim, {})
        groups.append(
            (
                (claim + 1) * 100,
                [
                    _pull(
                        10000 + claim * 100 + index,
                        rarity=6 if index in claim_sixes else 4,
                        item_id=claim_sixes.get(index, "four"),
                        item_type="weapon",
                        pool_version=version,
                    )
                    for index in range(10)
                ],
            )
        )
    return _pool(pool_id, groups, pool_type="weapon", up_six_chars=up_six_chars)


@pytest.mark.parametrize(
    ("pool_id", "pool_type", "item_type", "category", "is_rerun"),
    [
        ("rerun_chr_yvonne", "char", "char", "rerun", True),
        ("rerun_wpn_yvonne", "char", "char", "weapon", True),
        ("rerun_chr_mismatched", "weapon", "char", "weapon", True),
        ("unknown_weapon_id", "weapon", "weapon", "weapon", False),
        ("wepon_legacy", "char", "char", "weapon", False),
        ("weapon_current", "char", "char", "weapon", False),
        ("joint_current", "char", "char", "joint", False),
        ("special_current", "char", "char", "special", False),
        ("beginner", "char", "char", "beginner", False),
        ("standard", "char", "char", "standard", False),
    ],
)
def test_pool_classification_prioritizes_weapon_identity(app, pool_id, pool_type, item_type, category, is_rerun):
    pool = _pool(pool_id, [(100, [_pull(1000, item_type=item_type)])], pool_type=pool_type)

    assert pool.pool_category == category
    assert pool.is_rerun is is_rerun


def test_interleaved_rerun_characters_share_only_paid_small_pity(app):
    first = _pool(
        "rerun_chr_first",
        [
            (100, [_pull(101, rarity=6, item_id="up")]),
            (400, [_pull(104)]),
            (600, [_pull(106, rarity=6, item_id="up", is_free=True)]),
        ],
    )
    second = _pool("rerun_chr_second", [(300, [_pull(103)]), (500, [_pull(105)])])
    special = _pool("special_other", [(700, [_pull(107, rarity=6, item_id="up")])])
    view = _view(rerun_pools=[first, second], special_pools=[special])

    assert view.record.rerun_pity == 3
    assert view.record.special_pity == 0
    assert view.record.rerun_total_pulls == 5
    assert view.record.rerun_total_six == 2
    assert view.record.rerun_total_spook == 0
    assert view.record.rerun_up_avg == 1.0
    progress = {pool.pool.pool_id: pool.rerun_progress for pool in _pool_views(view)}
    assert next(category for category in view.categories if category.key == "rerun").pity_count == 3
    assert progress[first.pool_id].paid_count == 2
    assert progress[first.pool_id].up_obtained is True
    assert progress[first.pool_id].up_remaining == 0
    assert progress[second.pool_id].paid_count == 2
    assert progress[second.pool_id].up_obtained is False
    assert progress[second.pool_id].up_remaining == 118
    assert progress[special.pool_id] is None


@pytest.mark.parametrize("paid_count", [0, 29, 30, 59, 60, 89, 90, 119, 120, 239, 240, 479, 480])
def test_character_milestones_count_paid_draws_not_free_rewards(app, paid_count):
    pool = _pool(
        "rerun_chr_milestones",
        [
            (100, [_pull(index + 1000) for index in range(paid_count)]),
            (
                200,
                [_pull(index + 10000, rarity=6, item_id="up", is_free=True) for index in range(10)],
            ),
        ],
    )
    view = _view(rerun_pools=[pool])
    progress = _pool_views(view)[0].rerun_progress

    assert pool.total_pulls == paid_count + 10
    assert view.record.rerun_total_six == 10
    assert view.record.rerun_up_avg is None
    assert progress.paid_count == paid_count
    assert view.categories[0].pity_count == paid_count
    assert progress.up_obtained is False
    assert progress.up_remaining == max(0, 120 - paid_count)
    assert progress.free_ten_pulls_unlocked == min(3, paid_count // 30)
    assert progress.reward_count == paid_count // 240
    assert progress.next_reward_count == (paid_count // 240 + 1) * 240
    assert progress.reward_remaining == progress.next_reward_count - paid_count
    assert progress.next_reward_name == "UP信物"


def test_character_first_up_and_rewards_inherit_same_name_across_versions(app):
    pool = _pool(
        "rerun_chr_repeated",
        [
            (100, [_pull(index + 1000, pool_version=1) for index in range(60)]),
            (200, [_pull(index + 2000, pool_version=2) for index in range(60)]),
            (300, [_pull(3000, rarity=6, item_id="up", pool_version=2)]),
            (400, [_pull(index + 4000, pool_version=3) for index in range(120)]),
        ],
    )
    series = _pool_views(_view(rerun_pools=[pool]))[0]
    progress = series.rerun_progress

    assert series.periods[0].pool_version == 3
    assert progress.paid_count == 241
    assert progress.up_obtained is True
    assert progress.up_remaining == 0
    assert progress.free_ten_pulls_unlocked == 3
    assert progress.reward_count == 1
    assert progress.next_reward_count == 480


@pytest.mark.parametrize("weapon", [False, True])
def test_unknown_up_metadata_never_claims_guarantee_status(app, weapon):
    if weapon:
        pool = _weapon_pool([1] * 8, sixes={0: {0: "up"}}, up_six_chars=())
        view = _view(weapon_pools=[pool])
    else:
        pool = _pool("rerun_chr_unknown", [(100, [_pull(1, rarity=6, item_id="up")])], up_six_chars=())
        view = _view(rerun_pools=[pool])
    progress = _pool_views(view)[0].rerun_progress

    assert progress.up_obtained is None
    assert progress.up_remaining is None
    assert not pool.show_spook_stats
    assert all(
        not six.is_up and not six.is_spook
        for period in _pool_views(view)[0].periods
        for event in period.events
        for six in event.six_stars
    )
    if weapon:
        assert view.record.weapon_up_avg is None
        assert view.record.weapon_total_spook is None
        assert view.categories[0].average is None
        assert view.categories[0].spook_count is None
    else:
        assert view.record.rerun_up_avg is None
        assert view.record.rerun_total_spook is None


@pytest.mark.parametrize("claim_count", [3, 4, 7, 8])
def test_weapon_four_claim_pity_and_eight_claim_first_up_are_distinct(app, claim_count):
    pool = _weapon_pool([1] * claim_count)
    view = _view(weapon_pools=[pool])
    series = _pool_views(view)[0]
    progress = series.rerun_progress
    period = series.periods[0]

    assert pool.paid_pulls == claim_count * 10
    assert progress.paid_count == claim_count
    assert period.pity_count == claim_count
    assert progress.up_obtained is False
    assert progress.up_remaining == max(0, 8 - claim_count)
    assert progress.free_ten_pulls_unlocked is None
    assert view.categories[0].pity_count is None
    assert period.pity_limit == 4
    assert period.pity_unit == progress.unit == "次申领"
    assert series.six_star_limit == 40


@pytest.mark.parametrize(
    ("claim_count", "reward_count", "next_count", "next_name"),
    [
        (9, 0, 10, "补充武库箱"),
        (10, 1, 18, "UP武器"),
        (17, 1, 18, "UP武器"),
        (18, 2, 26, "补充武库箱"),
        (25, 2, 26, "补充武库箱"),
        (26, 3, 34, "UP武器"),
        (33, 3, 34, "UP武器"),
        (34, 4, 42, "补充武库箱"),
    ],
)
def test_weapon_reward_milestones_inherit_across_versions(app, claim_count, reward_count, next_count, next_name):
    pool = _weapon_pool([1] * 5 + [2] * (claim_count - 5))
    series = _pool_views(_view(weapon_pools=[pool]))[0]
    progress = series.rerun_progress

    assert series.periods[0].pool_version == 2
    assert progress.paid_count == claim_count
    assert series.periods[0].pity_count == claim_count - 5
    assert progress.reward_count == reward_count
    assert progress.next_reward_count == next_count
    assert progress.next_reward_name == next_name
    assert progress.reward_remaining == next_count - claim_count


def test_weapon_pity_resets_per_successful_batch_not_per_six_star_position(app):
    pool = _weapon_pool([1, 1, 1, 2, 2, 2], sixes={3: {1: "up", 8: "off"}})
    view = _view(weapon_pools=[pool])
    progress = _pool_views(view)[0].rerun_progress

    assert progress.paid_count == 6
    assert _pool_views(view)[0].periods[0].pity_count == 2
    assert progress.up_obtained is True
    assert progress.up_remaining == 0
    assert view.record.weapon_total_six == 2
    assert view.record.weapon_total_spook == 1
    assert view.record.weapon_up_avg == 32.0
    event = _pool_views(view)[0].periods[0].events[0]
    assert len(event.six_stars) == 2
    assert sorted(six.pity_count for six in event.six_stars) == [2, 7]


def test_weapon_first_up_remains_satisfied_in_later_same_name_version(app):
    pool = _weapon_pool([1] * 8 + [2] * 9, sixes={0: {5: "up"}})
    series = _pool_views(_view(weapon_pools=[pool]))[0]
    progress = series.rerun_progress

    assert progress.paid_count == 17
    assert series.periods[0].pool_version == 2
    assert series.periods[0].pity_count == 9
    assert progress.up_obtained is True
    assert progress.up_remaining == 0
    assert progress.reward_count == 1
    assert progress.next_reward_count == 18


@pytest.mark.parametrize(
    ("versions", "latest_version", "pity"),
    [
        ([1, 1, 1, 2, 2], 2, 2),
        ([1, 1, 1, None, None], None, None),
        ([None, None, None, 2, 2], 2, None),
        ([None, None, 1, 2, 2], 2, 2),
    ],
)
def test_weapon_unknown_versions_are_never_assumed_current(app, versions, latest_version, pity):
    pool = _weapon_pool(versions)
    view = _view(weapon_pools=[pool])
    progress = _pool_views(view)[0].rerun_progress

    period = _pool_views(view)[0].periods[0]
    assert period.pool_version == latest_version
    assert progress.paid_count == 5
    assert period.pity_count == pity
    assert progress.up_remaining == 3
    assert progress.reward_count == 0
    assert progress.next_reward_count == 10


def test_multiple_claims_with_same_second_and_sparse_sequences_count_actual_draws(app):
    paid = [
        _pull(
            9000 + index * 2,
            item_type="weapon",
            rarity=6 if index in {1, 8} else 4,
            item_id="up" if index in {1, 8} else "four",
        )
        for index in range(20)
    ]
    free = [_pull(10000 + index, item_type="weapon", rarity=6, item_id="up", is_free=True) for index in range(10)]
    pool = _pool("rerun_wpn_same_second", [(100, paid + free)], pool_type="weapon")
    view = _view(weapon_pools=[pool])
    progress = _pool_views(view)[0].rerun_progress

    assert pool.total_pulls == 30
    assert pool.paid_pulls == 20
    assert progress.paid_count == 2
    assert _pool_views(view)[0].periods[0].pity_count == 1
    assert progress.up_obtained is True
    assert progress.up_remaining == 0
    events = _pool_views(view)[0].periods[0].events
    assert len(events) == 2
    assert len(events[0].six_stars) == 2
    assert len(events[1].six_stars) == 10


@pytest.mark.parametrize("up_item", [None, "up"])
def test_incomplete_weapon_claims_make_cumulative_progress_unknown(app, up_item):
    pool = _weapon_pool([1])
    partial = [
        _pull(
            11000 + index,
            item_type="weapon",
            rarity=6 if up_item and index == 0 else 4,
            item_id=up_item if up_item and index == 0 else "four",
        )
        for index in range(5)
    ]
    groups = [(group.gacha_ts, group.pulls) for group in pool.records] + [(200, partial)]
    pool = _pool(pool.pool_id, groups, pool_type="weapon")
    view = _view(weapon_pools=[pool])
    progress = _pool_views(view)[0].rerun_progress

    assert pool.paid_pulls == 15
    assert progress.paid_count is None
    assert _pool_views(view)[0].periods[0].pity_count is None
    assert view.categories[0].pity_count is None
    assert progress.reward_count is None
    assert progress.next_reward_count is None
    assert progress.reward_remaining is None
    assert progress.up_obtained is bool(up_item)
    assert progress.up_remaining == (0 if up_item else None)


def test_incomplete_old_version_does_not_invent_cumulative_or_current_pity(app):
    pool = _pool(
        "rerun_wpn_partial_old",
        [
            (100, [_pull(1000 + index, item_type="weapon", pool_version=None) for index in range(5)]),
            (200, [_pull(2000 + index, item_type="weapon", pool_version=2) for index in range(10)]),
        ],
        pool_type="weapon",
    )
    series = _pool_views(_view(weapon_pools=[pool]))[0]
    progress = series.rerun_progress

    assert series.periods[0].pool_version == 2
    assert series.periods[0].pity_count is None
    assert progress.paid_count is None
    assert progress.up_remaining is None
    assert progress.reward_count is None


def test_latest_ordinary_weapon_pool_keeps_draw_based_pity(app):
    rerun = _weapon_pool([1] * 4)
    ordinary = _pool(
        "unknown_future_weapon",
        [(1000, [_pull(20000 + index, item_type="weapon") for index in range(7)])],
        pool_type="weapon",
    )
    view = _view(weapon_pools=[rerun, ordinary])

    assert _pool_views(view)[0].pool.pool_id == ordinary.pool_id
    assert _pool_views(view)[0].rerun_progress is None
    assert _pool_views(view)[0].six_star_limit == 80
    period = _pool_views(view)[0].periods[0]
    assert period.pity_count == 7
    assert period.pity_limit == 80
    assert period.pity_unit == "抽"
    assert [category.pity_count for category in view.categories] == [None, None]


def test_known_six_star_resets_pity_after_unknown_period_history(app):
    pool = _weapon_pool([None, None, 2, 2], sixes={2: {5: "up"}})
    series = _pool_views(_view(weapon_pools=[pool]))[0]
    progress = series.rerun_progress

    assert series.periods[0].pool_version == 2
    assert series.periods[0].pity_count == 1
    assert progress.paid_count == 4


def test_character_periods_keep_inherited_intervals_but_never_move_fives_between_versions(app):
    pool = _pool(
        "rerun_chr_periods",
        [
            (100, [_pull(1, rarity=5, item_id="v1_five"), _pull(2, rarity=6, item_id="first")]),
            (
                200,
                [
                    _pull(3, rarity=5, item_id="v1_tail"),
                    _pull(4, rarity=5, item_id="unknown_five", pool_version=None),
                    _pull(5, rarity=5, item_id="v2_five", pool_version=2),
                    _pull(6, rarity=6, item_id="second", pool_version=2),
                    _pull(7, rarity=6, item_id="free_first", pool_version=2, is_free=True),
                    _pull(8, rarity=6, item_id="free_last", pool_version=2, is_free=True),
                    _pull(9, rarity=5, item_id="free_five", pool_version=2, is_free=True),
                    _pull(10, rarity=6, item_id="unknown_free", pool_version=None, is_free=True),
                ],
            ),
            (
                300,
                [
                    _pull(11, rarity=6, item_id="unknown_paid", pool_version=None),
                    _pull(12, rarity=5, item_id="unknown_free_five", pool_version=None, is_free=True),
                ],
            ),
        ],
        up_six_chars=("first", "second"),
    )
    view = _view(rerun_pools=[pool])
    series = _pool_views(view)[0]
    periods = {period.pool_version: period for period in series.periods}

    assert [period.pool_version for period in series.periods] == [None, 2, 1]
    assert [
        (period.total_pulls, period.paid_pulls, period.free_pulls, period.six_count) for period in series.periods
    ] == [(4, 2, 2, 2), (5, 2, 3, 3), (3, 3, 0, 1)]
    assert sum(period.total_pulls for period in series.periods) == view.categories[0].total_pulls == 12
    assert sum(period.six_count for period in series.periods) == view.categories[0].six_count == 6
    assert series.rerun_progress.paid_count == 7
    first = periods[1].events[0].six_stars[0]
    second = periods[2].events[0].six_stars[0]
    unknown = periods[None].events[0].six_stars[0]
    assert (first.pity_count, second.pity_count, unknown.pity_count) == (2, 4, 1)
    assert [five.item_id for five in first.five_stars] == ["v1_five"]
    assert [five.item_id for five in second.five_stars] == ["v2_five"]
    assert [five.item_id for five in unknown.five_stars] == ["unknown_five"]
    free = periods[2].events[1]
    assert free.is_free
    assert free.pull_count == 3
    assert [six.item_id for six in free.six_stars] == ["free_last", "free_first"]
    assert all(six.pity_count is None and not six.five_stars for six in free.six_stars)
    assert [(five.item_id, five.count) for five in free.five_stars] == [("free_five", 1)]
    events = [event for period in series.periods for event in period.events]
    assert len({event.key for event in events}) == len(events)
    assert sum(len(event.six_stars) for event in events) == 6
    assert sum(event.pull_count for event in events if event.is_free) == 5


def test_same_second_weapon_periods_keep_atomic_golds_and_independent_claim_pity(app):
    def batch(start, version, *, sixes, fives=(), is_free=False):
        return [
            _pull(
                start + index,
                rarity=6 if index in sixes else 5 if index in fives else 4,
                item_id="up" if index in sixes else f"five_{version}" if index in fives else "four",
                item_type="weapon",
                pool_version=version,
                is_free=is_free,
            )
            for index in range(10)
        ]

    pool = _pool(
        "rerun_wpn_periods",
        [
            (
                100,
                batch(1000, 1, sixes={0}, fives={5})
                + batch(2000, 2, sixes={1, 8}, fives={0, 4})
                + batch(2100, 2, sixes={0, 9}, fives={5}, is_free=True)
                + batch(3000, None, sixes={4}, fives={1}),
            )
        ],
        pool_type="weapon",
    )
    view = _view(weapon_pools=[pool])
    series = _pool_views(view)[0]
    periods = {period.pool_version: period for period in series.periods}

    assert [period.pool_version for period in series.periods] == [None, 2, 1]
    assert [period.total_pulls for period in series.periods] == [10, 20, 10]
    assert [period.pity_count for period in series.periods] == [None, 0, 0]
    assert series.rerun_progress.paid_count == 3
    assert view.categories[0].pity_count is None
    assert (view.categories[0].total_pulls, view.categories[0].paid_pulls, view.categories[0].free_pulls) == (
        40,
        30,
        10,
    )
    assert all(period.pity_limit == 4 and period.pity_unit == "次申领" for period in series.periods)
    paid, free = periods[2].events
    assert not paid.is_free
    assert paid.pull_count == 10
    assert [six.pity_count for six in paid.six_stars] == [7, 2]
    assert [[five.item_id for five in six.five_stars] for six in paid.six_stars] == [["five_2"], ["five_2"]]
    assert free.is_free
    assert free.pull_count == 10
    assert len(free.six_stars) == 2
    assert all(six.pity_count is None for six in free.six_stars)
    assert periods[None].events[0].six_stars[0].pity_count is None
    events = [event for period in series.periods for event in period.events]
    assert len({event.key for event in events}) == len(events) == 4
    assert sum(period.six_count for period in series.periods) == sum(len(event.six_stars) for event in events) == 6
