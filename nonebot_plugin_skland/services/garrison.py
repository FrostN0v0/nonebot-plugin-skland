"""卫戍协议的账号级读取、对局归档和同局队友。"""

import asyncio
from dataclasses import asdict

from nonebot_plugin_orm import async_scoped_session

from ..schemas import CRED
from ..api import SklandAPI
from ..model import SkUser, Character, GarrisonMatch
from .auth import CredentialState, refresh_credentials
from ..db_handler import get_garrison_matches, get_garrison_scene_matches
from ..schemas.arknights.garrison import (
    GarrisonData,
    GarrisonRecord,
    GarrisonTeammate,
    GarrisonResources,
    GarrisonMatchStats,
)

_archive_lock = asyncio.Lock()


@refresh_credentials
async def fetch_garrison(
    user: SkUser | CredentialState,
    uid: str,
    *,
    activity_id: str | None = None,
) -> tuple[GarrisonData, GarrisonResources, str]:
    cred = CRED(cred=user.cred, token=user.cred_token)
    resources = await SklandAPI.ark_garrison_resources(cred, activity_id=activity_id)
    resolved_activity = activity_id or resources.current_activity_id
    data = await SklandAPI.ark_garrison(cred, uid=uid, activity_id=resolved_activity)
    return data, resources, resolved_activity


async def archive_garrison_matches(
    session: async_scoped_session, character_id: int, activity_id: str, data: GarrisonData
) -> None:
    matches: dict[str, tuple[GarrisonRecord, bool]] = {}
    for records, in_history in ((data.history.records, True), (data.history.favourRecords, False)):
        for record in records:
            if record.activityId == activity_id and record.id.strip():
                matches.setdefault(record.id, (record, in_history))
    badges = {badge.id: badge.masterVictor for badge in data.career.bandBadges}

    # Serialize the local read/merge/commit, not the upstream requests.
    async with _archive_lock:
        if (avatar := data.gameUserInfo.avatar) and (avatar_url := avatar.url.strip()):
            character = await session.get(Character, character_id)
            if character is not None and character.garrison_avatar_url != avatar_url:
                character.garrison_avatar_url = avatar_url
        if matches:
            existing = {
                row.record_id: row
                for row in await get_garrison_matches(character_id, activity_id, session, record_ids=list(matches))
            }
            for record_id, (record, in_history) in matches.items():
                row = existing.get(record_id)
                if row is not None and row.in_history and not in_history:
                    continue
                values = {
                    **asdict(GarrisonMatchStats.from_record(record)),
                    "scene_id": record.joint_scene_id,
                    "version_id": record.versionId,
                    "ended_at": record.gameEndTs,
                    "in_history": in_history,
                    "strategy_master_victor": badges.get(record.bandId),
                }
                if row is None:
                    session.add(
                        GarrisonMatch(character_id=character_id, activity_id=activity_id, record_id=record_id, **values)
                    )
                else:
                    for name, value in values.items():
                        if getattr(row, name) != value:
                            setattr(row, name, value)
        await session.commit()


async def get_archived_garrison_stats(
    session: async_scoped_session, character_id: int, activity_id: str, records: list[GarrisonRecord]
) -> list[GarrisonMatchStats]:
    by_id = {row.record_id: row for row in await get_garrison_matches(character_id, activity_id, session)}
    current = []
    for record in records:
        if record.activityId == activity_id and (row := by_id.pop(record.id, None)) is not None:
            current.append(row)
    return [
        GarrisonMatchStats(
            row.band_id,
            row.complete_state,
            row.duration_seconds,
            row.bond_layers,
            row.boss_kills,
            row.hidden_boss_kills,
        )
        for row in (*current, *by_id.values())
    ]


async def get_garrison_teammates(
    session: async_scoped_session,
    record: GarrisonRecord,
    resources: GarrisonResources,
    *,
    channel_master_id: str,
    uid: str,
) -> list[GarrisonTeammate]:
    if record.joint_scene_id is None or not record.activityId:
        return []
    seen = {(channel_master_id, uid)}
    teammates = []
    for row, channel, other_uid, nickname, avatar_url in await get_garrison_scene_matches(
        record.activityId, record.joint_scene_id, session
    ):
        if (
            (channel, other_uid) in seen
            or row.scene_id != record.joint_scene_id
            or row.activity_id != record.activityId
        ):
            continue
        seen.add((channel, other_uid))
        teammates.append(
            GarrisonTeammate.from_match(
                nickname,
                resources.for_version(row.version_id, row.activity_id),
                row.band_id,
                row.strategy_master_victor,
                row.bond_layers,
                avatar_url=avatar_url or "",
            )
        )
    return teammates
