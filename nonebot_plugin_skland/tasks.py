"""定时任务"""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from nonebot import get_bots, logger
from nonebot.compat import model_dump
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_orm import get_scoped_session

from .model import SkUser
from .api import SklandAPI
from .config import CACHE_DIR
from .schemas import CRED, ArkSignResponse, EndfieldSignResponse
from .db_handler import (
    select_all_users,
    get_endfield_characters,
    get_arknights_characters,
    select_enabled_campaign_reminders,
)
from .commands.campaign import build_merged_campaign_reminder_message, gather_campaign_reminder_groups
from .utils import refresh_cred_token_with_error_return, refresh_access_token_with_error_return


@refresh_cred_token_with_error_return
@refresh_access_token_with_error_return
async def _ark_sign_in(user: SkUser, uid: str, channel_master_id: str) -> ArkSignResponse:
    """执行明日方舟签到逻辑"""
    cred = CRED(cred=user.cred, token=user.cred_token)
    return await SklandAPI.ark_sign(cred, uid, channel_master_id=channel_master_id)


@refresh_cred_token_with_error_return
@refresh_access_token_with_error_return
async def _endfield_sign_in(user: SkUser, role_id: str, server_id: str) -> EndfieldSignResponse:
    """执行终末地签到逻辑"""
    cred = CRED(cred=user.cred, token=user.cred_token)
    return await SklandAPI.endfield_sign(cred, role_id, server_id=server_id)


@scheduler.scheduled_job(
    "cron",
    day_of_week="sun",
    hour="12,18",
    minute=0,
    timezone=ZoneInfo("Asia/Shanghai"),
    id="campaign_reminder",
)
async def run_campaign_reminder():
    """Check default character campaign rewards on Sunday noon and evening"""
    session = get_scoped_session()
    try:
        bots = get_bots()
        if not bots:
            logger.warning("Campaign reminder skipped: no connected bot")
            return

        reminders = await select_enabled_campaign_reminders(session)
        for group_result in await gather_campaign_reminder_groups(session, reminders):
            target = group_result.target
            bot = bots.get(target.self_id) if target.self_id else None
            if bot is None:
                bot = next(iter(bots.values()))

            message = build_merged_campaign_reminder_message(group_result.pending)
            try:
                await message.send(target=target, bot=bot)
            except Exception as e:
                user_ids = ", ".join(item.platform_user_id for item in group_result.pending)
                logger.warning(f"Campaign reminder send failed for group {target.id} users [{user_ids}]: {e}")
    finally:
        await session.close()


@scheduler.scheduled_job("cron", hour=0, minute=15, id="daily_arksign")
async def run_daily_arksign():
    """明日方舟每日自动签到"""
    session = get_scoped_session()
    sign_result: dict[str, ArkSignResponse | str] = {}
    serializable_sign_result: dict[str, dict | str] = {}
    for user in await select_all_users(session):
        characters = await get_arknights_characters(user, session)
        for character in characters:
            sign_result[character.nickname] = await _ark_sign_in(user, str(character.uid), character.channel_master_id)
    serializable_sign_result["data"] = {
        nickname: model_dump(res) if isinstance(res, ArkSignResponse) else res for nickname, res in sign_result.items()
    }
    serializable_sign_result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    sign_result_file = CACHE_DIR / "sign_result.json"
    if not sign_result_file.exists():
        sign_result_file.parent.mkdir(parents=True, exist_ok=True)
    with open(sign_result_file, "w", encoding="utf-8") as f:
        json.dump(serializable_sign_result, f, ensure_ascii=False, indent=2)
    await session.close()


@scheduler.scheduled_job("cron", hour=0, minute=20, id="daily_efsign")
async def run_daily_efsign():
    """终末地每日自动签到"""
    session = get_scoped_session()
    sign_result: dict[str, EndfieldSignResponse | str] = {}
    serializable_sign_result: dict[str, dict | str] = {}
    for user in await select_all_users(session):
        characters = await get_endfield_characters(user, session)
        for character in characters:
            sign_result[character.nickname] = await _endfield_sign_in(
                user, character.role_id, character.channel_master_id
            )
    serializable_sign_result["data"] = {
        nickname: model_dump(res) if isinstance(res, EndfieldSignResponse) else res
        for nickname, res in sign_result.items()
    }
    serializable_sign_result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    sign_result_file = CACHE_DIR / "endfield_sign_result.json"
    if not sign_result_file.exists():
        sign_result_file.parent.mkdir(parents=True, exist_ok=True)
    with open(sign_result_file, "w", encoding="utf-8") as f:
        json.dump(serializable_sign_result, f, ensure_ascii=False, indent=2)
    await session.close()
