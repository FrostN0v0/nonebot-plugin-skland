"""抽卡记录命令"""

import asyncio

from nonebot import logger
from nonebot.adapters import Bot
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, CustomNode, UniMessage

from ..config import config
from ..model import GachaRecord
from ..schemas import GachaInfo
from ..player_data import get_ark_card
from ..render import render_gacha_history
from ..api import SklandAPI, SklandLoginAPI
from .selection import check_user_character
from ..db_handler import get_character_gacha_records
from ..utils.message import send_reaction, send_request_error
from ..exception import SklandException, UnresolvedGachaCharacterError
from ..services.gacha import (
    group_gacha_records,
    get_all_gacha_records,
    heybox_data_to_record,
    import_heybox_gacha_data,
)


async def gacha_handler(
    user_session: UserSession,
    session: async_scoped_session,
    begin: Match[int],
    limit: Match[int],
    target: Match[At | int],
    bot: Bot,
    *,
    role_index: int | None = None,
):
    """查询明日方舟抽卡记录"""

    if target.available:
        target_platform_id = target.result.target if isinstance(target.result, At) else target.result
        target_id = (await get_user(user_session.platform, str(target_platform_id))).id
    else:
        target_id = user_session.user_id

    selected = await check_user_character(target_id, user_session, session, app_code="arknights", role_index=role_index)
    if selected is None:
        return
    user, character = selected
    send_reaction(user_session, "processing")
    if not user.access_token:
        await session.rollback()
        await UniMessage("当前角色所属账号未保存 token,请使用 token 或扫码更新该账号").send(at_sender=True)
        return
    grant_code = await SklandLoginAPI.get_grant_code(user.access_token, 1)
    role_token = await SklandLoginAPI.get_role_token_by_uid(character.uid, grant_code)
    ak_cookie = await SklandLoginAPI.get_ak_cookie(role_token)
    categories = await SklandAPI.get_gacha_categories(character.uid, role_token, user.access_token, ak_cookie)
    all_gacha_records_flat: list[GachaInfo] = []

    for cate in categories:
        count_before = len(all_gacha_records_flat)
        async for record in get_all_gacha_records(character, cate, user.access_token, role_token, ak_cookie):
            all_gacha_records_flat.append(record)
        count_after = len(all_gacha_records_flat)
        new_records_count = count_after - count_before
        cate_name = cate.name.replace("\n", "")
        logger.debug(
            f"正在获取角色：{character.nickname} 的抽卡记录，"
            f"卡池类别：{cate_name}, 本次获取记录条数: {new_records_count}"
        )
    records = await get_character_gacha_records(character.id, session)
    existing_records_set = {(r.gacha_ts, r.pos) for r in records}
    record_to_save: list[GachaRecord] = []
    for gacha_record in all_gacha_records_flat:
        record = GachaRecord(
            character_id=character.id,
            pool_id=gacha_record.poolId,
            pool_name=gacha_record.poolName,
            char_id=gacha_record.charId,
            char_name=gacha_record.charName,
            rarity=gacha_record.rarity,
            is_new=gacha_record.isNew,
            gacha_ts=gacha_record.gacha_ts_sec,
            pos=gacha_record.pos,
        )
        if (int(gacha_record.gacha_ts_sec), gacha_record.pos) in existing_records_set:
            continue
        record_to_save.append(record)

    all_gacha_records = records + record_to_save

    gacha_data_grouped = group_gacha_records(all_gacha_records)
    character_nickname = character.nickname
    character_channel_master_id = character.channel_master_id
    session.add_all(record_to_save)
    try:
        user_info = await get_ark_card(user, character)
    except SklandException as error:
        await session.commit()
        await send_request_error(error)
        return
    except Exception:
        # Fetched pulls and any refreshed credentials are valid even if the profile response is not.
        await session.commit()
        raise
    await session.commit()
    if not user_info:
        return
    gacha_limit = limit.result if limit.available else None
    gacha_begin = begin.result if begin.available else None
    start, stop, _ = slice(gacha_begin, gacha_limit).indices(len(gacha_data_grouped.pools))
    selected_count = max(0, stop - start)
    page_size = config.gacha_render_max
    if selected_count > page_size:
        await UniMessage.text("抽卡记录过多，将以多张图片形式发送").send(reply_to=True)
        if user_session.platform == "QQClient":
            render_semaphore = asyncio.Semaphore(4)

            async def render(page_start: int) -> bytes:
                async with render_semaphore:
                    return await render_gacha_history(
                        gacha_data_grouped,
                        user_info.status,
                        nickname=character_nickname,
                        channel_master_id=character_channel_master_id,
                        begin=page_start,
                        limit=min(page_start + page_size, stop),
                    )

            page_starts = range(start, stop, page_size)
            imgs = await asyncio.gather(*(render(page_start) for page_start in page_starts))
            nodes = []
            for page_start, content in zip(page_starts, imgs):
                page_stop = min(page_start + page_size, stop)
                nodes.append(
                    CustomNode(
                        bot.self_id,
                        f"{character_nickname} | {page_start}-{page_stop}",
                        UniMessage.image(raw=content),
                    )
                )
            await UniMessage.reference(*nodes).send()
        else:
            send_lock = asyncio.Lock()

            async def send(img: bytes) -> None:
                async with send_lock:  # ensure msg sequence
                    await UniMessage.image(raw=img).send()

            tasks: list[asyncio.Task] = []
            for page_start in range(start, stop, page_size):
                page_stop = min(page_start + page_size, stop)
                img = await render_gacha_history(
                    gacha_data_grouped,
                    user_info.status,
                    nickname=character_nickname,
                    channel_master_id=character_channel_master_id,
                    begin=page_start,
                    limit=page_stop,
                )
                tasks.append(asyncio.create_task(send(img)))
            await asyncio.gather(*tasks)
    else:
        await UniMessage.image(
            raw=await render_gacha_history(
                gacha_data_grouped,
                user_info.status,
                nickname=character_nickname,
                channel_master_id=character_channel_master_id,
                begin=start,
                limit=stop,
            )
        ).send()
    send_reaction(user_session, "done")


async def import_handler(
    url: Match[str],
    user_session: UserSession,
    session: async_scoped_session,
    *,
    role_index: int | None = None,
):
    """导入明日方舟抽卡记录"""
    selected = await check_user_character(
        user_session.user_id, user_session, session, app_code="arknights", role_index=role_index
    )
    if selected is None:
        return
    _user, character = selected
    if url.available:
        import_result = await import_heybox_gacha_data(url.result)
        if str(import_result["info"]["uid"]) == character.uid:
            try:
                records = heybox_data_to_record(import_result["data"], character.id)
            except UnresolvedGachaCharacterError as error:
                send_reaction(user_session, "fail")
                await UniMessage(f"以下干员无法识别：{'、'.join(error.names)}，请让管理员更新数据资源后重新导入").send(
                    at_sender=True
                )
                return
            db_records = await get_character_gacha_records(character.id, session)
            existing_records_set = {(r.gacha_ts, r.pos) for r in db_records}
            record_to_save: list[GachaRecord] = []
            for record in records:
                if (record.gacha_ts, record.pos) in existing_records_set:
                    continue
                record_to_save.append(record)
            logger.debug(f"读取抽卡记录共 {len(records)} 条, 其中导入 {len(record_to_save)} 条新记录")
            session.add_all(record_to_save)
            await UniMessage(f"导入成功，读取抽卡记录共 {len(records)} 条, 共导入 {len(record_to_save)} 条新记录").send(
                at_sender=True
            )
            send_reaction(user_session, "done")
            await session.commit()
        else:
            send_reaction(user_session, "fail")
            await UniMessage("导入的抽卡记录与当前角色不匹配").finish(at_sender=True)
