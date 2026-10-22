"""Layout-independent Endfield gacha history projection."""

from pydantic import BaseModel

from .base import EfGachaPull, EfGachaGroup
from .pool import EfGachaPoolInfo
from .statistics import EfGroupedGachaRecord


class EfGachaFiveStar(BaseModel):
    item_id: str
    item_name: str
    count: int


class EfGachaSixStar(BaseModel):
    item_id: str
    item_name: str
    is_new: bool
    is_up: bool
    is_spook: bool
    pity_count: int | None
    five_stars: list[EfGachaFiveStar]


class EfGachaEvent(BaseModel):
    """An atomic paid batch with six-stars, or any free batch."""

    key: str
    gacha_ts: int
    is_free: bool
    pull_count: int
    six_stars: list[EfGachaSixStar]
    five_stars: list[EfGachaFiveStar]


class EfRerunProgress(BaseModel):
    """Observed series-wide milestones, not a claim/reward receipt ledger."""

    unit: str
    paid_count: int | None
    up_obtained: bool | None
    up_remaining: int | None
    free_ten_pulls_unlocked: int | None
    reward_count: int | None
    next_reward_count: int | None
    next_reward_name: str

    @property
    def reward_remaining(self) -> int | None:
        if self.paid_count is None or self.next_reward_count is None:
            return None
        return self.next_reward_count - self.paid_count


class EfPeriodView(BaseModel):
    key: str
    pool_version: int | None
    events: list[EfGachaEvent]
    total_pulls: int
    paid_pulls: int
    free_pulls: int
    six_count: int
    spook_count: int | None
    pity_count: int | None
    pity_limit: int
    pity_unit: str


class EfPoolView(BaseModel):
    pool: EfGachaPoolInfo
    periods: list[EfPeriodView]
    rerun_progress: EfRerunProgress | None = None
    six_star_limit: int = 80


class EfCategoryView(BaseModel):
    key: str
    title: str
    total_pulls: int
    paid_pulls: int
    free_pulls: int
    six_count: int
    spook_count: int | None
    average: float | None
    average_label: str
    pity_count: int | None
    pity_limit: int
    pity_unit: str
    pity_label: str
    pools: list[EfPoolView]


class EfGachaView(BaseModel):
    """Selected history with unsliced category and series statistics."""

    record: EfGroupedGachaRecord
    nickname: str
    role_id: str
    server_name: str
    avatar_url: str = ""
    new_count: int = 0
    is_cached: bool = False
    notice: str = ""
    categories: list[EfCategoryView]

    @classmethod
    def from_record(
        cls,
        record: EfGroupedGachaRecord,
        *,
        nickname: str,
        role_id: str,
        server_name: str,
        avatar_url: str = "",
        new_count: int = 0,
        is_cached: bool = False,
        notice: str = "",
        begin: int | None = None,
        limit: int | None = None,
    ) -> "EfGachaView":
        categories = []
        for key, title, pools in (
            ("special", "限定寻访", record.special_pools),
            ("rerun", "重构寻访", record.rerun_pools),
            ("weapon", "武器申领", record.ordinary_weapon_pools),
            ("rerun_weapon", "重构武器申领", record.rerun_weapon_pools),
            ("joint", "联合寻访", record.joint_pools),
            ("standard", "基础寻访", record.standard_pools),
            ("beginner", "启程寻访", record.beginner_pools),
        ):
            if not any(pool.total_pulls for pool in pools):
                continue
            categories.append(_project_category(record, key, title, pools, begin=begin, limit=limit))
        return cls(
            record=record,
            nickname=nickname,
            role_id=role_id,
            server_name=server_name,
            avatar_url=avatar_url,
            new_count=new_count,
            is_cached=is_cached,
            notice=notice,
            categories=categories,
        )


def _project_category(
    record: EfGroupedGachaRecord,
    key: str,
    title: str,
    pools: list[EfGachaPoolInfo],
    *,
    begin: int | None,
    limit: int | None,
) -> EfCategoryView:
    weapon = key in {"weapon", "rerun_weapon"}
    up_average = key in {"special", "rerun", "weapon", "rerun_weapon"}
    if weapon:
        average = record.paid_up_average(pools)
        pity_count = None
    else:
        average = getattr(record, f"{key}_{'up' if up_average else 'six'}_avg", None)
        pity_count = pools[0].pity_count if key == "beginner" else getattr(record, f"{key}_pity")
    spook_counts = [pool.total_six_spook for pool in pools] if up_average else []
    spook_count = (
        sum(count for count in spook_counts if count is not None)
        if spook_counts and all(count is not None for count in spook_counts)
        else None
    )
    # Build each complete series before selecting it. Neither category totals nor
    # period attribution/intervals depend on the requested display range.
    projected_pools = [_project_pool(pool) for pool in pools]
    return EfCategoryView(
        key=key,
        title=title,
        total_pulls=sum(pool.total_pulls for pool in pools),
        paid_pulls=sum(pool.paid_pulls for pool in pools),
        free_pulls=sum(pool.free_pulls for pool in pools),
        six_count=sum(pool.total_six_stars for pool in pools),
        spook_count=spook_count,
        average=average,
        average_label="UP平均" if up_average else "6★平均",
        pity_count=pity_count,
        pity_limit=4 if key == "rerun_weapon" else 40 if key == "beginner" else 80,
        pity_unit="次申领" if key == "rerun_weapon" else "抽",
        pity_label="" if weapon else "已垫抽数",
        pools=projected_pools[begin:limit],
    )


def _add_five_star(five_stars: dict[str, EfGachaFiveStar], pull: EfGachaPull) -> None:
    existing = five_stars.get(pull.item_id)
    if existing is None:
        five_stars[pull.item_id] = EfGachaFiveStar(item_id=pull.item_id, item_name=pull.item_name, count=1)
    else:
        existing.count += 1


def _rerun_progress(pool: EfGachaPoolInfo) -> EfRerunProgress | None:
    if not pool.is_rerun:
        return None

    weapon = pool.pool_category == "weapon"
    paid_count = pool.rerun_weapon_claim_count if weapon else pool.paid_pulls
    paid_up_count = pool.paid_up_six_stars
    up_obtained = bool(paid_up_count) if paid_up_count is not None else None
    up_remaining = None
    if up_obtained:
        up_remaining = 0
    elif up_obtained is False and paid_count is not None:
        up_remaining = max(0, (8 if weapon else 120) - paid_count)

    reward_count = None
    next_reward_count = None
    next_reward_name = "补充武库箱 / UP武器" if weapon else "UP信物"
    if paid_count is not None:
        if weapon:
            reward_count = max(0, (paid_count - 10) // 8 + 1)
            next_reward_count = 10 + reward_count * 8
            next_reward_name = "补充武库箱" if reward_count % 2 == 0 else "UP武器"
        else:
            reward_count = paid_count // 240
            next_reward_count = (reward_count + 1) * 240

    return EfRerunProgress(
        unit="次申领" if weapon else "抽",
        paid_count=paid_count,
        up_obtained=up_obtained,
        up_remaining=up_remaining,
        free_ten_pulls_unlocked=None if weapon else min(3, pool.paid_pulls // 30),
        reward_count=reward_count,
        next_reward_count=next_reward_count,
        next_reward_name=next_reward_name,
    )


def _period_pools(pool: EfGachaPoolInfo) -> dict[int | None, EfGachaPoolInfo]:
    if not pool.is_rerun:
        return {None: pool}
    records: dict[int | None, list[EfGachaGroup]] = {}
    for group in pool.records:
        by_version: dict[int | None, list[EfGachaPull]] = {}
        for pull in group.pulls:
            by_version.setdefault(pull.pool_version, []).append(pull)
        for version, pulls in by_version.items():
            records.setdefault(version, []).append(EfGachaGroup(gacha_ts=group.gacha_ts, pulls=pulls))
    return {version: pool.model_copy(update={"records": groups}) for version, groups in records.items()}


def _project_pool(pool: EfGachaPoolInfo) -> EfPoolView:
    rerun_weapon = pool.is_rerun and pool.pool_category == "weapon"
    periods: dict[int | None, EfPeriodView] = {}
    for version, period_pool in _period_pools(pool).items():
        suffix = f"v{version}" if version is not None else "unknown" if pool.is_rerun else "all"
        periods[version] = EfPeriodView(
            key=f"{pool.pool_id}:{suffix}",
            pool_version=version,
            events=[],
            total_pulls=period_pool.total_pulls,
            paid_pulls=period_pool.paid_pulls,
            free_pulls=period_pool.free_pulls,
            six_count=period_pool.total_six_stars,
            spook_count=period_pool.total_six_spook if period_pool.show_spook_stats else None,
            pity_count=(
                pool.rerun_weapon_period_pity(version)
                if rerun_weapon
                else period_pool.pity_count
                if pool.pool_category == "weapon"
                else None
            ),
            pity_limit=4 if rerun_weapon else 80,
            pity_unit="次申领" if rerun_weapon else "抽",
        )

    complete_weapon_pulls = (
        {pull.seq_id: len(batch) == 10 for batch in pool.rerun_weapon_batches for pull in batch} if rerun_weapon else {}
    )
    pending_fives: dict[int | None, dict[str, EfGachaFiveStar]] = {}
    pity_count: int | None = 0
    previous_version: int | None = None
    has_previous_paid = False
    up_six_chars = set(pool.up_six_chars)
    show_spook = pool.show_spook_stats

    # Scan the full series chronologically. Character intervals inherit earlier
    # periods, while five-stars and atomic paid/free events stay in their period.
    for group in reversed(pool.records):
        paid_events: dict[int | None, EfGachaEvent] = {}
        free_events: dict[int | None, EfGachaEvent] = {}
        free_fives: dict[int | None, dict[str, EfGachaFiveStar]] = {}
        for pull in reversed(group.pulls):
            version = pull.pool_version if pool.is_rerun else None
            period = periods[version]
            events = free_events if pull.is_free else paid_events
            event = events.get(version)
            if event is None:
                event = EfGachaEvent(
                    key=f"{period.key}:{group.gacha_ts}:{'free' if pull.is_free else 'paid'}",
                    gacha_ts=group.gacha_ts,
                    is_free=pull.is_free,
                    pull_count=0,
                    six_stars=[],
                    five_stars=[],
                )
                events[version] = event
            event.pull_count += 1
            fives = free_fives.setdefault(version, {}) if pull.is_free else pending_fives.setdefault(version, {})
            if not pull.is_free:
                if rerun_weapon:
                    if version is None:
                        pity_count = None
                    elif not has_previous_paid or previous_version != version:
                        pity_count = None if has_previous_paid and previous_version is None else 0
                    if not complete_weapon_pulls[pull.seq_id]:
                        pity_count = None
                    previous_version = version
                    has_previous_paid = True
                if pity_count is not None:
                    pity_count += 1

            if pull.rarity == 5:
                _add_five_star(fives, pull)
            elif pull.rarity == 6:
                event.six_stars.append(
                    EfGachaSixStar(
                        item_id=pull.item_id,
                        item_name=pull.item_name,
                        is_new=pull.is_new,
                        is_up=pull.item_id in up_six_chars,
                        is_spook=show_spook and pull.item_id not in up_six_chars,
                        pity_count=None if pull.is_free else pity_count,
                        five_stars=[] if pull.is_free else [fives[key] for key in sorted(fives)],
                    )
                )
                if not pull.is_free:
                    pity_count = (
                        0 if not rerun_weapon or (complete_weapon_pulls[pull.seq_id] and version is not None) else None
                    )
                    fives.clear()

        # Reverse each completed period below, leaving paid before free for a
        # mixed timestamp without joining different versions or splitting golds.
        for version, event in free_events.items():
            event.six_stars.reverse()
            event.five_stars = [free_fives[version][key] for key in sorted(free_fives[version])]
            periods[version].events.append(event)
        for version, event in paid_events.items():
            if event.six_stars:
                event.six_stars.reverse()
                periods[version].events.append(event)

    for period in periods.values():
        period.events.reverse()
    return EfPoolView(
        pool=pool,
        periods=list(periods.values()),
        rerun_progress=_rerun_progress(pool),
        six_star_limit=40 if rerun_weapon else 80,
    )
