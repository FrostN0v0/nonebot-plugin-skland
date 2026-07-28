from __future__ import annotations

import asyncio
from time import monotonic
from dataclasses import dataclass
from collections import OrderedDict
from collections.abc import Callable, Awaitable

from .api import SklandAPI
from .config import config
from .schemas import CRED, ArkCard
from .model import SkUser, Character
from .utils import refresh_cred_token_if_needed, refresh_access_token_if_needed

ArkCardLoader = Callable[[SkUser, Character], Awaitable[ArkCard | None]]
Clock = Callable[[], float]


@dataclass(frozen=True, slots=True)
class _ArkCardCacheKey:
    user_id: int
    account_id: str | None
    app_code: str
    channel_master_id: str
    uid: str
    role_id: str | None
    generation: int


@dataclass(slots=True)
class _ArkCardCacheEntry:
    value: ArkCard
    expires_at: float


class ArkCardDataSource:
    def __init__(
        self,
        *,
        ttl: int,
        max_entries: int,
        loader: ArkCardLoader,
        clock: Clock = monotonic,
    ) -> None:
        self._ttl = ttl
        self._max_entries = max_entries
        self._loader = loader
        self._clock = clock
        self._cache: OrderedDict[_ArkCardCacheKey, _ArkCardCacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._inflight: dict[_ArkCardCacheKey, asyncio.Task[ArkCard | None]] = {}
        self._generations: dict[int, int] = {}

    def _prune_generation_if_unused(self, user_id: int) -> None:
        if any(key.user_id == user_id for key in self._cache):
            return
        if any(key.user_id == user_id for key in self._inflight):
            return
        self._generations.pop(user_id, None)

    def _purge_expired(self, now: float) -> None:
        expired_keys = [key for key, entry in self._cache.items() if now >= entry.expires_at]
        expired_user_ids = {key.user_id for key in expired_keys}
        for key in expired_keys:
            del self._cache[key]
        for user_id in expired_user_ids:
            self._prune_generation_if_unused(user_id)

    def _key(self, user: SkUser, character: Character) -> _ArkCardCacheKey:
        return _ArkCardCacheKey(
            user_id=user.id,
            account_id=user.user_id,
            app_code=character.app_code,
            channel_master_id=character.channel_master_id,
            uid=str(character.uid),
            role_id=character.role_id,
            generation=self._generations.get(user.id, 0),
        )

    async def _load(self, key: _ArkCardCacheKey, user: SkUser, character: Character) -> ArkCard | None:
        try:
            value = await self._loader(user, character)
            if value is None:
                return None

            async with self._lock:
                now = self._clock()
                self._purge_expired(now)
                if self._generations.get(key.user_id, 0) == key.generation:
                    self._cache[key] = _ArkCardCacheEntry(value=value, expires_at=now + self._ttl)
                    self._cache.move_to_end(key)
                    while len(self._cache) > self._max_entries:
                        evicted_key, _ = self._cache.popitem(last=False)
                        self._prune_generation_if_unused(evicted_key.user_id)
            return value
        finally:
            current_task = asyncio.current_task()
            async with self._lock:
                if self._inflight.get(key) is current_task:
                    del self._inflight[key]
                self._prune_generation_if_unused(key.user_id)

    async def get(self, user: SkUser, character: Character) -> ArkCard | None:
        async with self._lock:
            now = self._clock()
            self._purge_expired(now)
            key = self._key(user, character)
            entry = self._cache.get(key)
            if entry is not None:
                self._cache.move_to_end(key)
                return entry.value

            task = self._inflight.get(key)
            if task is None:
                task = asyncio.create_task(self._load(key, user, character))
                task.add_done_callback(_consume_task_exception)
                self._inflight[key] = task

        return await asyncio.shield(task)

    async def invalidate_user(self, user_id: int) -> None:
        async with self._lock:
            self._generations[user_id] = self._generations.get(user_id, 0) + 1
            stale_keys = [key for key in self._cache if key.user_id == user_id]
            for key in stale_keys:
                del self._cache[key]
            self._prune_generation_if_unused(user_id)


def _consume_task_exception(task: asyncio.Task[ArkCard | None]) -> None:
    if not task.cancelled():
        task.exception()


async def _load_ark_card(user: SkUser, character: Character) -> ArkCard:
    return await SklandAPI.ark_card(CRED(cred=user.cred, token=user.cred_token), str(character.uid))


ark_card_data = ArkCardDataSource(
    ttl=config.ark_card_cache_ttl,
    max_entries=config.ark_card_cache_max_entries,
    loader=_load_ark_card,
)


@refresh_cred_token_if_needed
@refresh_access_token_if_needed
async def get_ark_card(user: SkUser, character: Character) -> ArkCard | None:
    return await ark_card_data.get(user, character)
