"""Layout-independent Endfield gacha history projection."""

from pydantic import BaseModel

from .base import EfGachaPull
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


class EfPoolView(BaseModel):
    pool: EfGachaPoolInfo
    events: list[EfGachaEvent]


class EfGachaView(BaseModel):
    """Selected history with the unsliced cumulative statistics."""

    record: EfGroupedGachaRecord
    nickname: str
    role_id: str
    server_name: str
    avatar_url: str = ""
    new_count: int = 0
    is_cached: bool = False
    notice: str = ""
    pools: list[EfPoolView]

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
        visible_pool_ids = record.get_visible_pool_ids(begin, limit)
        return cls(
            record=record,
            nickname=nickname,
            role_id=role_id,
            server_name=server_name,
            avatar_url=avatar_url,
            new_count=new_count,
            is_cached=is_cached,
            notice=notice,
            pools=[_project_pool(pool) for pool in record.flat_pools if pool.pool_id in visible_pool_ids],
        )


def _add_five_star(five_stars: dict[str, EfGachaFiveStar], pull: EfGachaPull) -> None:
    existing = five_stars.get(pull.item_id)
    if existing is None:
        five_stars[pull.item_id] = EfGachaFiveStar(item_id=pull.item_id, item_name=pull.item_name, count=1)
    else:
        existing.count += 1


def _project_pool(pool: EfGachaPoolInfo) -> EfPoolView:
    events: list[EfGachaEvent] = []
    pending_fives: dict[str, EfGachaFiveStar] = {}
    pity_count = 0
    up_six_chars = set(pool.up_six_chars)
    show_spook = pool.show_spook_stats

    # Existing models keep groups and pulls newest-first. Accumulate each paid
    # interval chronologically, independently of free pulls and other pools.
    for group in reversed(pool.records):
        paid_count = 0
        free_count = 0
        paid_sixes: list[EfGachaSixStar] = []
        free_sixes: list[EfGachaSixStar] = []
        free_fives: dict[str, EfGachaFiveStar] = {}
        for pull in reversed(group.pulls):
            if pull.is_free:
                free_count += 1
            else:
                paid_count += 1
                pity_count += 1

            if pull.rarity == 5:
                _add_five_star(free_fives if pull.is_free else pending_fives, pull)
            elif pull.rarity == 6:
                six = EfGachaSixStar(
                    item_id=pull.item_id,
                    item_name=pull.item_name,
                    is_new=pull.is_new,
                    is_up=pull.item_id in up_six_chars,
                    is_spook=show_spook and pull.item_id not in up_six_chars,
                    pity_count=None if pull.is_free else pity_count,
                    five_stars=[] if pull.is_free else [pending_fives[key] for key in sorted(pending_fives)],
                )
                if pull.is_free:
                    free_sixes.append(six)
                else:
                    paid_sixes.append(six)
                    pity_count = 0
                    pending_fives.clear()

        # Reverse the completed event list below: paid precedes free for a mixed
        # timestamp, matching the previous history presentation.
        if free_count:
            free_sixes.reverse()
            events.append(
                EfGachaEvent(
                    key=f"{pool.pool_id}:{group.gacha_ts}:free",
                    gacha_ts=group.gacha_ts,
                    is_free=True,
                    pull_count=free_count,
                    six_stars=free_sixes,
                    five_stars=[free_fives[key] for key in sorted(free_fives)],
                )
            )
        if paid_sixes:
            paid_sixes.reverse()
            events.append(
                EfGachaEvent(
                    key=f"{pool.pool_id}:{group.gacha_ts}:paid",
                    gacha_ts=group.gacha_ts,
                    is_free=False,
                    pull_count=paid_count,
                    six_stars=paid_sixes,
                    five_stars=[],
                )
            )

    events.reverse()
    return EfPoolView(pool=pool, events=events)
