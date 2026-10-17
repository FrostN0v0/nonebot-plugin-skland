from nonebot import logger
from sqlalchemy import update
from nonebot.adapters import Bot
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, CustomNode, UniMessage

from ...model import SkUser
from ...api import SklandAPI
from ...exception import SklandException
from ...schemas import CRED, EfGachaView
from ...utils.message import send_reaction
from ..selection import check_user_character
from ...data_source import ef_gacha_pool_data
from ...render import render_ef_gacha_history
from ...db_handler import get_character_gacha_records
from ...services.auth import CredentialState, refresh_credentials
from ...services.gacha import sync_ef_gacha_records, group_ef_gacha_records


async def ef_gacha_history_handler(
    user_session: UserSession,
    session: async_scoped_session,
    begin: Match[int],
    limit: Match[int],
    target: Match[At | int],
    bot: Bot,
    *,
    role_index: int | None = None,
):
    """Synchronize the selected role's history, then present detached paged statistics."""
    if target.available:
        target_platform_id = target.result.target if isinstance(target.result, At) else target.result
        target_id = (await get_user(user_session.platform, str(target_platform_id))).id
    else:
        target_id = user_session.user_id

    selected = await check_user_character(target_id, user_session, session, app_code="endfield", role_index=role_index)
    if selected is None:
        return
    user, character = selected
    if not user.skland_user_id:
        await session.rollback()
        await UniMessage("账号身份尚未同步,请先执行 sk char update").send(at_sender=True)
        return

    # No ORM identity is consulted after the read transaction ends.
    account_id, owner_id = user.id, user.owner_id
    remote_user_id = user.skland_user_id
    credentials = CredentialState(user.access_token, user.cred, user.cred_token)
    original_credentials = (credentials.cred, credentials.cred_token)
    character_id, uid = character.id, character.uid
    role_id, server_id = character.role_id, character.channel_master_id
    nickname, server_name = character.nickname, character.server_name
    platform = user_session.platform
    await session.rollback()
    send_reaction(user_session, "processing")

    new_count = 0
    is_cached = False
    notice = ""
    gacha_data = None
    if credentials.access_token:
        try:
            gacha_data, new_count = await sync_ef_gacha_records(
                session,
                character_id=character_id,
                uid=uid,
                server_id=server_id,
                access_token=credentials.access_token,
            )
        except SklandException as error:
            await session.rollback()
            logger.warning(f"Endfield history sync failed: {type(error).__name__}")
            notice = "抽卡记录同步失败，请稍后重试或更新账号凭证"
    else:
        notice = "当前角色所属账号未保存 token,请使用 token 或扫码更新该账号"

    if gacha_data is None:
        cached_records = await get_character_gacha_records(character_id, session)
        gacha_data = group_ef_gacha_records(cached_records)
        await session.rollback()
        if not gacha_data.total_pulls:
            await UniMessage(notice).send(at_sender=True)
            return
        is_cached = True
        notice = f"{notice}；本次仅展示本地缓存，可能不是最新记录"
    if not gacha_data.total_pulls:
        await UniMessage.text("已同步，暂无抽卡记录").send(reply_to=True)
        return

    for pool in gacha_data.special_pools + gacha_data.joint_pools + gacha_data.weapon_pools:
        local_pool = ef_gacha_pool_data.get_pool(pool.pool_id)
        if local_pool:
            pool.up_six_chars = local_pool.up_six_char_ids
            pool.up6_img = local_pool.up6_image or local_pool.rotate_image
            pool.up6_name = local_pool.up_six_display_name
        else:
            try:
                content = await SklandAPI.get_ef_gacha_content(pool.pool_id, server_id)
                pool.up_six_chars = content.pool.up_six_char_ids
                pool.up6_img = content.pool.up6_image or content.pool.rotate_image
                pool.up6_name = content.pool.up_six_display_name
            except Exception as error:
                logger.warning(f"Endfield pool metadata unavailable: {type(error).__name__}")

    @refresh_credentials
    async def get_user_info(state: CredentialState):
        return await SklandAPI.endfield_card(
            CRED(cred=state.cred, token=state.cred_token),
            user_id=remote_user_id,
            role_id=role_id,
            server_id=server_id,
        )

    avatar_url = ""
    try:
        user_info = await get_user_info(credentials)
        if user_info:
            avatar_url = user_info.base.avatarUrl
    except Exception as error:
        # Profile data is decorative; history has already been committed.
        logger.warning(f"Endfield profile unavailable: {type(error).__name__}")
    finally:
        if (credentials.cred, credentials.cred_token) != original_credentials:
            await session.execute(
                update(SkUser)
                .where(SkUser.id == account_id, SkUser.owner_id == owner_id)
                .values(cred=credentials.cred, cred_token=credentials.cred_token)
                .execution_options(synchronize_session=False)
            )
            await session.commit()

    view = EfGachaView.from_record(
        gacha_data,
        nickname=nickname,
        role_id=role_id,
        server_name=server_name,
        avatar_url=avatar_url,
        new_count=new_count,
        is_cached=is_cached,
        notice=notice,
        begin=begin.result if begin.available else None,
        limit=limit.result if limit.available else None,
    )
    images = await render_ef_gacha_history(view)
    if len(images) == 1:
        await UniMessage.image(raw=images[0]).send(at_sender=True)
    elif platform == "QQClient":
        nodes = [
            CustomNode(bot.self_id, f"{nickname} | 第 {index} 页", UniMessage.image(raw=content))
            for index, content in enumerate(images, 1)
        ]
        await UniMessage.reference(*nodes).send()
    else:
        for content in images:
            await UniMessage.image(raw=content).send()

    logger.info(
        f"{nickname} 的终末地抽卡统计: "
        f"总计 {gacha_data.total_pulls} 抽 "
        f"(角色池 {gacha_data.char_total_pulls} + 武器池 {gacha_data.weapon_total_pulls}), "
        f"本次新增 {new_count} 条记录"
    )
    send_reaction(user_session, "done")
