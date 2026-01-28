"""抽卡记录命令"""

import asyncio

from nonebot import logger
from nonebot.adapters import Bot
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, CustomNode, UniMessage

from ..config import config
from ..schemas import CRED, GachaInfo
from ..render import render_gacha_history
from ..api import SklandAPI, SklandLoginAPI
from ..model import SkUser, Character, GachaRecord
from ..db_handler import select_all_gacha_records, get_default_arknights_character
from ..utils import (
    send_reaction,
    group_gacha_records,
    get_all_gacha_records,
    heybox_data_to_record,
    import_heybox_gacha_data,
    refresh_cred_token_if_needed,
    refresh_access_token_if_needed,
)


async def check_user_character(user_id: int, session: async_scoped_session) -> tuple[SkUser, Character]:
    """检查用户和角色绑定状态"""
    user = await session.get(SkUser, user_id)
    if not user:
        await UniMessage("未绑定 skland 账号").finish(at_sender=True)
    char = await get_default_arknights_character(user, session)
    if not char:
        await UniMessage("未绑定 arknights 账号").finish(at_sender=True)
    return user, char


async def gacha_handler(
    user_session: UserSession,
    session: async_scoped_session,
    begin: Match[int],
    limit: Match[int],
    target: Match[At | int],
    bot: Bot,
):
    """查询明日方舟抽卡记录"""

    @refresh_cred_token_if_needed
    @refresh_access_token_if_needed
    async def get_user_info(user: SkUser, uid: str):
        return await SklandAPI.ark_card(CRED(cred=user.cred, token=user.cred_token), uid)

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
    records = await select_all_gacha_records(user, character.uid, session)
    existing_records_set = {(r.gacha_ts, r.pos) for r in records}
    gacha_record_list: list[GachaRecord] = []
    record_to_save: list[GachaRecord] = []
    for gacha_record in all_gacha_records_flat:
        record = GachaRecord(
            uid=user.id,
            char_pk_id=character.id,
            char_uid=character.uid,
            pool_id=gacha_record.poolId,
            pool_name=gacha_record.poolName,
            char_id=gacha_record.charId,
            char_name=gacha_record.charName,
            rarity=gacha_record.rarity,
            is_new=gacha_record.isNew,
            gacha_ts=gacha_record.gacha_ts_sec,
            pos=gacha_record.pos,
        )
        gacha_record_list.append(record)
        if (int(gacha_record.gacha_ts_sec), gacha_record.pos) in existing_records_set:
            continue
        record_to_save.append(record)

    all_gacha_records = records + record_to_save

    gacha_data_grouped = group_gacha_records(all_gacha_records)
    user_info = await get_user_info(user, character.uid)
    if not user_info:
        return
    gacha_limit = limit.result if limit.available else None
    gacha_begin = begin.result if begin.available else None
    if len(gacha_data_grouped.pools[gacha_begin:gacha_limit]) > config.gacha_render_max:
        await UniMessage.text("抽卡记录过多，将以多张图片形式发送").send(reply_to=True)
        if user_session.platform == "QQClient":
            render_semaphore = asyncio.Semaphore(4)

            async def render(index: int) -> bytes:
                async with render_semaphore:
                    return await render_gacha_history(
                        gacha_data_grouped, character, user_info.status, index, index + config.gacha_render_max
                    )

            imgs = await asyncio.gather(
                *(
                    render(i)
                    for i in range(
                        gacha_begin if gacha_begin is not None else 0,
                        len(gacha_data_grouped.pools[gacha_begin:gacha_limit]),
                        config.gacha_render_max,
                    )
                )
            )
            gacha_begin_val = gacha_begin if gacha_begin is not None else 0
            total = len(gacha_data_grouped.pools[gacha_begin:gacha_limit])
            nodes = []
            for index, content in enumerate(imgs, 1):
                start_id = gacha_begin_val + (index - 1) * config.gacha_render_max

                if index * config.gacha_render_max >= total:
                    end_id = gacha_begin_val + total
                else:
                    end_id = gacha_begin_val + index * config.gacha_render_max
                nodes.append(
                    CustomNode(
                        bot.self_id,
                        f"{character.nickname} | {start_id}-{end_id}",
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
            for i in range(
                gacha_begin if gacha_begin is not None else 0,
                len(gacha_data_grouped.pools[gacha_begin:gacha_limit]),
                config.gacha_render_max,
            ):
                img = await render_gacha_history(
                    gacha_data_grouped, character, user_info.status, i, i + config.gacha_render_max
                )
                tasks.append(asyncio.create_task(send(img)))
            await asyncio.gather(*tasks)
    else:
        await UniMessage.image(
            raw=await render_gacha_history(gacha_data_grouped, character, user_info.status, gacha_begin, gacha_limit)
        ).send()
    send_reaction(user_session, "done")
    session.add_all(record_to_save)
    await session.commit()


async def import_handler(url: Match[str], user_session: UserSession, session: async_scoped_session):
    """导入明日方舟抽卡记录"""
    user, character = await check_user_character(user_session.user_id, session)
    if url.available:
        import_result = await import_heybox_gacha_data(url.result)
        if str(import_result["info"]["uid"]) == character.uid:
            records = heybox_data_to_record(import_result["data"], user.id, character.id, character.uid)
            db_records = await select_all_gacha_records(user, character.uid, session)
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
