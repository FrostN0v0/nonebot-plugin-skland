from nonebot import logger
from nonebot.adapters import Bot
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, UniMessage

from ...model import GachaRecord
from .utils import check_user_character
from ...api import SklandAPI, SklandLoginAPI
from ...schemas import EfGachaInfo, EndfieldPoolType
from ...db_handler import select_all_ef_gacha_records
from ...utils import (
    send_reaction,
    group_ef_gacha_records,
    get_all_ef_gacha_records,
)

# 需要遍历的角色池类型
EF_CHAR_POOL_TYPES = [
    EndfieldPoolType.STANDARD,
    EndfieldPoolType.SPECIAL,
    EndfieldPoolType.BEGINNER,
]


async def ef_gacha_history_handler(
    user_session: UserSession,
    session: async_scoped_session,
    begin: Match[int],
    limit: Match[int],
    target: Match[At | int],
    bot: Bot,
):
    """查询终末地抽卡记录"""

    if target.available:
        target_platform_id = target.result.target if isinstance(target.result, At) else target.result
        target_id = (await get_user(user_session.platform, str(target_platform_id))).id
    else:
        target_id = user_session.user_id

    user, character = await check_user_character(target_id, session)
    send_reaction(user_session, "processing")
    token = user.access_token
    grant_code = await SklandLoginAPI.get_grant_code(token, 1)
    role_token = await SklandLoginAPI.get_role_token_by_uid(character.uid, grant_code)

    # ── 获取所有角色池记录 ──
    all_gacha_records_flat: list[EfGachaInfo] = []
    # 构建 API 返回记录的 is_free 映射，用于修正数据库中旧记录
    api_is_free_map: dict[tuple[int, int], bool] = {}
    for pool_type in EF_CHAR_POOL_TYPES:
        count_before = len(all_gacha_records_flat)
        async for record in get_all_ef_gacha_records(character, pool_type, role_token):
            all_gacha_records_flat.append(record)
            api_is_free_map[(record.gacha_ts_sec, record.seq_id_int)] = record.is_free_pull
        new_count = len(all_gacha_records_flat) - count_before
        logger.debug(
            f"正在获取角色：{character.nickname} 的终末地抽卡记录，"
            f"卡池类型：{pool_type.name}, 本次获取记录条数: {new_count}"
        )

    # ── 获取武器池记录 ──
    count_before = len(all_gacha_records_flat)
    async for record in get_all_ef_gacha_records(character, EndfieldPoolType.WEAPON, role_token):
        all_gacha_records_flat.append(record)
        api_is_free_map[(record.gacha_ts_sec, record.seq_id_int)] = record.is_free_pull
    weapon_count = len(all_gacha_records_flat) - count_before
    logger.debug(f"正在获取角色：{character.nickname} 的终末地武器池抽卡记录，本次获取记录条数: {weapon_count}")

    # ── 去重 + 构建 GachaRecord + 修正旧记录 is_free ──
    db_records = await select_all_ef_gacha_records(user, character.uid, session)
    existing_records_set = {(r.gacha_ts, r.pos) for r in db_records}

    record_to_save: list[GachaRecord] = []
    for gacha_record in all_gacha_records_flat:
        if (gacha_record.gacha_ts_sec, gacha_record.seq_id_int) in existing_records_set:
            continue
        record = GachaRecord(
            uid=user.id,
            char_pk_id=character.id,
            char_uid=character.uid,
            app_code="endfield",
            item_type=gacha_record.item_type,
            pool_id=gacha_record.poolId,
            pool_name=gacha_record.poolName,
            char_id=gacha_record.item_id,
            char_name=gacha_record.item_name,
            rarity=gacha_record.rarity,
            is_new=gacha_record.isNew,
            is_free=gacha_record.is_free_pull,
            gacha_ts=gacha_record.gacha_ts_sec,
            pos=gacha_record.seq_id_int,
        )
        record_to_save.append(record)

    all_gacha_records = db_records + record_to_save

    # ── 分组 ──
    gacha_data = group_ef_gacha_records(all_gacha_records)

    # 获取每个 SPECIAL 卡池的 UP 角色信息
    for pool in gacha_data.special_pools:
        try:
            content = await SklandAPI.get_ef_gacha_content(pool.pool_id, character.channel_master_id)
            pool.up_six_chars = content.pool.up_six_char_ids
            logger.debug(f"卡池 {pool.pool_name}({pool.pool_id}) UP六星: {pool.up_six_chars}")
        except Exception as e:
            logger.warning(f"获取卡池 {pool.pool_name} UP信息失败: {e}")

    total = gacha_data.total_pulls
    char_total = gacha_data.char_total_pulls
    weapon_total = gacha_data.weapon_total_pulls
    new_count = len(record_to_save)

    msg_lines = [
        f"📊 {character.nickname} 的终末地抽卡统计",
        f"🎰 总计: {total} 抽 (角色池 {char_total} + 武器池 {weapon_total})",
        f"🆕 本次新增: {new_count} 条记录",
        f"🏭 武库配额: 产出 {gacha_data.char_arsenal_quota_earned}"
        f" | 消耗 {gacha_data.weapon_arsenal_quota_consumed}"
        f" | 净值 {gacha_data.arsenal_quota_net}",
    ]

    # BEGINNER 池信息
    if gacha_data.beginner_pools:
        bg = gacha_data.beginner_pools[0]
        msg_lines.append(
            f"🌟 新手池: {bg.total_pulls}/40 抽, 6⭐×{bg.total_six_stars}, 产出配额 {bg.arsenal_quota_earned}"
        )

    # STANDARD 池信息
    if gacha_data.standard_pools:
        sp = gacha_data.standard_pools[0]
        pity_remaining = gacha_data.standard_pity_remaining
        msg_lines.append(
            f"📦 常驻池: {sp.total_pulls} 抽, "
            f"{pity_remaining}次寻访内必出6⭐, "
            f"垫{sp.pity_count}"
            f", 产出配额 {sp.arsenal_quota_earned}"
        )

    # SPECIAL 池信息（跨池小保底 + 每池大保底）
    if gacha_data.special_pools:
        small_remaining = gacha_data.special_pity_remaining
        msg_lines.append(f"🎯 限定池: {gacha_data.special_total_pulls} 抽, {small_remaining}次寻访内必出6⭐")
        for pool in gacha_data.special_pools:
            parts = [f"  ├ {pool.pool_name}: {pool.total_pulls} 抽"]
            parts.append(f"垫{pool.pity_count}")
            # UP保底信息
            if pool.up_six_chars:
                if pool.has_pulled_up_six:
                    parts.append("已获得UP")
                else:
                    up_remaining = gacha_data.special_pool_up_pity_remaining(pool)
                    parts.append(f"距UP保底 {up_remaining} 抽")
            parts.append(f"产出配额 {pool.arsenal_quota_earned}")
            msg_lines.append(", ".join(parts))

    # 武器池信息（各池独立）
    if gacha_data.weapon_pools:
        for pool in gacha_data.weapon_pools:
            msg_lines.append(
                f"🗡️ {pool.pool_name}: {pool.total_pulls} 抽, "
                f"垫 {pool.pity_count} 抽, "
                f"消耗配额 {pool.arsenal_quota_consumed}"
            )

    await UniMessage("\n".join(msg_lines)).send(at_sender=True)
    send_reaction(user_session, "done")

    # ── 保存 ──
    session.add_all(record_to_save)
    await session.commit()
