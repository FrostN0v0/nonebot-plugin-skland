import asyncio

from nonebot import logger
from nonebot.adapters import Bot
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, CustomNode, UniMessage

from ...config import config
from .utils import check_user_character
from ...api import SklandAPI, SklandLoginAPI
from ...data_source import ef_gacha_pool_data
from ...render import render_ef_gacha_history
from ...model import SkUser, Character, GachaRecord
from ...db_handler import select_all_ef_gacha_records
from ...schemas import CRED, EfGachaInfo, EndfieldPoolType, EndfieldCharPoolType
from ...utils import (
    send_reaction,
    group_ef_gacha_records,
    get_all_ef_gacha_records,
    refresh_cred_token_if_needed,
    refresh_access_token_if_needed,
)

# 需要遍历的角色池类型
EF_CHAR_POOL_TYPES: list[EndfieldCharPoolType] = [
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
    update: bool = False,
):
    """查询终末地抽卡记录

    Args:
        update: 是否从接口拉取最新数据并更新，默认仅从数据库读取渲染
    """

    @refresh_cred_token_if_needed
    @refresh_access_token_if_needed
    async def get_user_info(user: SkUser, char: Character):
        return await SklandAPI.endfield_card(CRED(cred=user.cred, token=user.cred_token), user.user_id, char)

    if target.available:
        target_platform_id = target.result.target if isinstance(target.result, At) else target.result
        target_id = (await get_user(user_session.platform, str(target_platform_id))).id
    else:
        target_id = user_session.user_id

    user, character = await check_user_character(target_id, session)
    send_reaction(user_session, "processing")

    new_count = 0
    if update:
        # ── 从接口拉取最新数据 ──
        token = user.access_token
        grant_code = await SklandLoginAPI.get_grant_code(token, 1)
        role_token = await SklandLoginAPI.get_role_token_by_uid(character.uid, grant_code)

        # 获取所有角色池记录
        all_gacha_records_flat: list[EfGachaInfo] = []
        for pool_type in EF_CHAR_POOL_TYPES:
            records = await get_all_ef_gacha_records(character, pool_type, role_token)
            all_gacha_records_flat.extend(records)
            logger.debug(
                f"正在获取角色：{character.nickname} 的终末地抽卡记录，"
                f"卡池类型：{pool_type.name}, 本次获取记录条数: {len(records)}"
            )

        # 获取武器池记录
        records = await get_all_ef_gacha_records(character, EndfieldPoolType.WEAPON, role_token)
        all_gacha_records_flat.extend(records)
        logger.debug(f"正在获取角色：{character.nickname} 的终末地武器池抽卡记录，本次获取记录条数: {len(records)}")

        # 去重 + 构建 GachaRecord
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
        new_count = len(record_to_save)
    else:
        # ── 仅从数据库读取 ──
        all_gacha_records = await select_all_ef_gacha_records(user, character.uid, session)
        if not all_gacha_records:
            await UniMessage.text("暂无抽卡记录，请先使用 -u 参数从接口拉取数据").send(reply_to=True)
            return
        record_to_save = []

    # ── 分组 ──
    gacha_data = group_ef_gacha_records(all_gacha_records)

    # 获取每个 SPECIAL 卡池的 UP 角色信息
    for pool in gacha_data.special_pools + gacha_data.weapon_pools:
        # 优先从本地卡池数据查询 UP 信息
        local_pool = ef_gacha_pool_data.get_pool(pool.pool_id)
        if local_pool:
            pool.up_six_chars = local_pool.up_six_char_ids
            pool.up6_img = local_pool.up6_image or local_pool.rotate_image
            pool.up6_name = local_pool.up6_name
            logger.debug(f"卡池 {pool.pool_name}({pool.pool_id}) UP六星(本地): {pool.up_six_chars}")
        else:
            # 本地无数据时 fallback 到实时 API
            try:
                content = await SklandAPI.get_ef_gacha_content(pool.pool_id, character.channel_master_id)
                pool.up_six_chars = content.pool.up_six_char_ids
                pool.up6_img = content.pool.up6_image or content.pool.rotate_image
                pool.up6_name = content.pool.up6_name
                logger.debug(f"卡池 {pool.pool_name}({pool.pool_id}) UP六星(API): {pool.up_six_chars}")
            except Exception as e:
                logger.warning(f"获取卡池 {pool.pool_name} UP信息失败: {e}")

    total = gacha_data.total_pulls
    char_total = gacha_data.char_total_pulls
    weapon_total = gacha_data.weapon_total_pulls
    new_count = len(record_to_save)

    user_info = await get_user_info(user, character)
    if not user_info:
        await UniMessage.text("获取用户信息失败，无法渲染抽卡记录").send(reply_to=True)
        return

    # ── 渲染图片（分页） ──
    gacha_begin = begin.result if begin.available else None
    gacha_limit = limit.result if limit.available else None
    render_max = config.ef_gacha_render_max

    # begin/limit 对各类别分别计数，取最大值判断是否需要分页
    effective_start = gacha_begin if gacha_begin is not None else 0
    max_end = gacha_data.max_category_pool_count
    effective_end = min(gacha_limit, max_end) if gacha_limit is not None else max_end
    page_pool_count = max(0, effective_end - effective_start)

    if page_pool_count > render_max:
        await UniMessage.text("抽卡记录过多，将以多张图片形式发送").send(reply_to=True)

        if user_session.platform == "QQClient":
            render_semaphore = asyncio.Semaphore(4)

            async def render(idx: int) -> bytes:
                async with render_semaphore:
                    return await render_ef_gacha_history(
                        gacha_data, user_info.base, character, idx, min(idx + render_max, effective_end)
                    )

            imgs = await asyncio.gather(*(render(i) for i in range(effective_start, effective_end, render_max)))
            nodes = []
            for index, content in enumerate(imgs, 1):
                s = effective_start + (index - 1) * render_max
                e = min(effective_start + index * render_max, effective_end)
                nodes.append(
                    CustomNode(
                        bot.self_id,
                        f"{character.nickname} | 卡池 {s + 1}-{e}",
                        UniMessage.image(raw=content),
                    )
                )
            await UniMessage.reference(*nodes).send()
        else:
            send_lock = asyncio.Lock()

            async def send(img: bytes) -> None:
                async with send_lock:
                    await UniMessage.image(raw=img).send()

            tasks: list[asyncio.Task] = []
            for i in range(effective_start, effective_end, render_max):
                img = await render_ef_gacha_history(
                    gacha_data, user_info.base, character, i, min(i + render_max, effective_end)
                )
                tasks.append(asyncio.create_task(send(img)))
            await asyncio.gather(*tasks)
    else:
        img = await render_ef_gacha_history(gacha_data, user_info.base, character, gacha_begin, gacha_limit)
        await UniMessage.image(raw=img).send(at_sender=True)

    logger.info(
        f"{character.nickname} 的终末地抽卡统计: "
        f"总计 {total} 抽 (角色池 {char_total} + 武器池 {weapon_total}), "
        f"本次新增 {new_count} 条记录"
    )
    send_reaction(user_session, "done")

    # ── 保存 ──
    session.add_all(record_to_save)
    await session.commit()
