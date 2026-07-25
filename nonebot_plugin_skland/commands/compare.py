"""Operator training compare video command."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timedelta

from nonebot import logger
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, UniMessage

from ..api import SklandAPI
from ..config import CACHE_DIR
from .card import check_user_character
from ..exception import RequestException
from ..data_source import gacha_table_data
from ..filters import ark_skin_illust_url
from ..render import render_compare_cover, render_compare_operator
from ..utils import (
    send_reaction,
    refresh_cred_token_if_needed,
    refresh_access_token_if_needed,
)
from ..video import (
    COVER_DURATION,
    OPERATOR_FRAME_DURATION,
    FFmpegNotFoundError,
    require_ffmpeg,
    encode_slideshow,
)
from ..schemas import (
    CRED,
    Status,
    ArkCard,
    OperatorCard,
    OperatorRoster,
    OperatorRosterQuery,
    OperatorCatalogEntry,
)

MIN_TARGETS = 2
MAX_TARGETS = 6
COMPARE_CACHE_DIR = CACHE_DIR / "compare"
COMPARE_CACHE_TTL = timedelta(hours=24)


@dataclass(slots=True)
class ComparePlayer:
    status: Status
    cover_bg: str
    cards_by_id: dict[str, OperatorCard]


def platform_id_of(target: At | int) -> str:
    return str(target.target) if isinstance(target, At) else str(target)


def dedupe_targets(targets: tuple[At | int, ...] | list[At | int]) -> list[At | int]:
    """Keep first occurrence order while dropping duplicate platform ids."""
    seen: set[str] = set()
    result: list[At | int] = []
    for target in targets:
        key = platform_id_of(target)
        if key in seen:
            continue
        seen.add(key)
        result.append(target)
    return result


def six_star_entries(
    catalog_entries: tuple[OperatorCatalogEntry, ...] | list[OperatorCatalogEntry],
) -> list[OperatorCatalogEntry]:
    """All six-star catalog entries sorted by reverse release (ascending sort_id)."""
    return sorted(
        (entry for entry in catalog_entries if entry.star == 6),
        key=lambda entry: (entry.sort_id, entry.char_id),
    )


def compare_query(catalog) -> OperatorRosterQuery:
    return OperatorRosterQuery.from_input(
        catalog,
        ownership="all",
        rarities="6",
        sort="release",
    )


def cover_background_of(info: ArkCard) -> str:
    if info.status.secretary and info.status.secretary.skinId:
        return ark_skin_illust_url(info.status.secretary.skinId)
    if info.assistChars:
        return ark_skin_illust_url(info.assistChars[0].skinId)
    return ""


def build_player_cache(info: ArkCard, catalog, query: OperatorRosterQuery) -> ComparePlayer:
    roster = OperatorRoster.build(
        status=info.status,
        catalog=catalog,
        characters=info.chars,
        query=query,
        equipment_map=info.equipmentInfoMap,
    )
    return ComparePlayer(
        status=info.status,
        cover_bg=cover_background_of(info),
        cards_by_id={card.char_id: card for card in roster.cards},
    )


def aligned_operator_cards(
    players: list[ComparePlayer],
    entry: OperatorCatalogEntry,
) -> list[OperatorCard]:
    cards: list[OperatorCard] = []
    for player in players:
        card = player.cards_by_id.get(entry.char_id)
        if card is None:
            card = OperatorCard.from_entry(entry, None)
        cards.append(card)
    return cards


def purge_expired_compare_cache(now: datetime | None = None) -> None:
    """Remove compare videos older than COMPARE_CACHE_TTL."""
    if not COMPARE_CACHE_DIR.exists():
        return
    cutoff = (now or datetime.now()).timestamp() - COMPARE_CACHE_TTL.total_seconds()
    for path in COMPARE_CACHE_DIR.glob("*.mp4"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError as error:
            logger.debug(f"compare cache cleanup skipped {path}: {error}")


def build_compare_cache_path(players: list[ComparePlayer]) -> Path:
    COMPARE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    purge_expired_compare_cache()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uids = "-".join(player.status.uid for player in players)
    return COMPARE_CACHE_DIR / f"compare_{stamp}_{uids}.mp4"


async def send_compare_video(cache_path: Path) -> None:
    """Send the generated compare clip as a file upload."""
    size_mb = cache_path.stat().st_size / (1024 * 1024)
    logger.debug(f"compare video cached at: {cache_path} ({size_mb:.1f} MiB)")
    try:
        await UniMessage.file(path=str(cache_path), name="operator_compare.mp4").send()
    except Exception as error:
        logger.debug(f"compare video send as file failed: {error}")
        await UniMessage.text(f"文件发送失败：{error}，已缓存：{cache_path}").finish(at_sender=True)


@refresh_cred_token_if_needed
@refresh_access_token_if_needed
async def _fetch_ark_card(user, uid: str):
    return await SklandAPI.ark_card(CRED(cred=user.cred, token=user.cred_token), uid)


async def _resolve_platform_user_id(user_session: UserSession, target: At | int) -> int:
    return (await get_user(user_session.platform, platform_id_of(target))).id


async def compare_handler(
    session: async_scoped_session,
    user_session: UserSession,
    targets: Match[tuple[At | int, ...]],
):
    """Build a six-star training compare slideshow for 2-6 bound players."""
    if not targets.available or not targets.result:
        await UniMessage.text("请至少 @ 2 名已绑定用户").finish(at_sender=True)
        return

    unique_targets = dedupe_targets(targets.result)
    if len(unique_targets) < MIN_TARGETS:
        await UniMessage.text(f"练度对比至少需要 {MIN_TARGETS} 名用户（去重后不足）").finish(at_sender=True)
        return
    if len(unique_targets) > MAX_TARGETS:
        await UniMessage.text(f"练度对比最多支持 {MAX_TARGETS} 名用户").finish(at_sender=True)
        return

    try:
        require_ffmpeg()
    except FFmpegNotFoundError as error:
        await UniMessage.text(str(error)).finish(at_sender=True)
        return

    if not gacha_table_data.operator_catalog.entries:
        try:
            gacha_table_data.load_operator_catalog()
        except RequestException as error:
            await UniMessage.text(str(error)).finish(at_sender=True)
            return

    catalog = gacha_table_data.operator_catalog
    query = compare_query(catalog)
    entries = six_star_entries(catalog.entries)
    if not entries:
        await UniMessage.text("当前图鉴中没有六星干员数据").finish(at_sender=True)
        return

    send_reaction(user_session, "processing")
    await UniMessage.text(
        f"正在生成 {len(unique_targets)} 人练度对比视频（封面 + {len(entries)} 个六星），请稍候…"
    ).send(reply_to=True)

    players: list[ComparePlayer] = []
    for target in unique_targets:
        target_id = await _resolve_platform_user_id(user_session, target)
        user, ark_character = await check_user_character(target_id, session)
        info = await _fetch_ark_card(user, str(ark_character.uid))
        if not info:
            send_reaction(user_session, "done")
            return
        players.append(build_player_cache(info, catalog, query))

    try:
        cover = await render_compare_cover(players)
        semaphore = asyncio.Semaphore(4)
        progress_lock = asyncio.Lock()
        completed = 0
        total_frames = len(entries)

        async def render_operator_frame(entry: OperatorCatalogEntry) -> bytes:
            nonlocal completed
            async with semaphore:
                frame = await render_compare_operator(
                    players=players,
                    cards=aligned_operator_cards(players, entry),
                    operator_name=entry.name,
                )
            async with progress_lock:
                completed += 1
                if completed % 10 == 0 or completed == total_frames:
                    logger.debug(f"compare operator frames: {completed}/{total_frames}")
            return frame

        operator_frames = await asyncio.gather(*(render_operator_frame(entry) for entry in entries))
    except Exception as error:
        send_reaction(user_session, "done")
        await UniMessage.text(f"渲染失败：{error}").finish(at_sender=True)
        return

    with tempfile.TemporaryDirectory(prefix="skland-compare-") as tmp:
        tmp_dir = Path(tmp)
        frame_paths: list[tuple[Path, float]] = []

        cover_path = tmp_dir / "frame_000.png"
        cover_path.write_bytes(cover)
        frame_paths.append((cover_path, COVER_DURATION))

        for index, payload in enumerate(operator_frames, start=1):
            path = tmp_dir / f"frame_{index:03d}.png"
            path.write_bytes(payload)
            frame_paths.append((path, OPERATOR_FRAME_DURATION))

        cache_path = build_compare_cache_path(players)
        try:
            await encode_slideshow(frame_paths, cache_path)
        except Exception as error:
            logger.debug(f"compare video encode failed: {error}")
            cache_path.unlink(missing_ok=True)
            send_reaction(user_session, "done")
            await UniMessage.text(f"视频合成失败：{error}").finish(at_sender=True)
            return

    send_reaction(user_session, "done")
    await send_compare_video(cache_path)
    await session.commit()
