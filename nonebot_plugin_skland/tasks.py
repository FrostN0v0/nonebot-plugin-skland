"""定时任务"""

import json
from datetime import datetime

from nonebot.compat import model_dump
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_orm import get_scoped_session

from .model import SkUser
from .api import SklandAPI
from .config import CACHE_DIR
from .schemas import CRED, ArkSignResponse, EndfieldSignResponse
from .db_handler import select_all_users, get_endfield_characters, get_arknights_characters
from .utils import refresh_cred_token_with_error_return, refresh_access_token_with_error_return


@refresh_cred_token_with_error_return
@refresh_access_token_with_error_return
async def _ark_sign_in(user: SkUser, uid: str, channel_master_id: str) -> ArkSignResponse:
    """执行明日方舟签到逻辑"""
    cred = CRED(cred=user.cred, token=user.cred_token)
    return await SklandAPI.ark_sign(cred, uid, channel_master_id=channel_master_id)


@refresh_cred_token_with_error_return
@refresh_access_token_with_error_return
async def _endfield_sign_in(user: SkUser, uid: str, server_id: str) -> EndfieldSignResponse:
    """执行终末地签到逻辑"""
    cred = CRED(cred=user.cred, token=user.cred_token)
    return await SklandAPI.endfield_sign(cred, uid, server_id=server_id)


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


@scheduler.scheduled_job("cron", hour=0, minute=20, id="daily_zmdsign")
async def run_daily_zmdsign():
    """终末地每日自动签到"""
    session = get_scoped_session()
    sign_result: dict[str, EndfieldSignResponse | str] = {}
    serializable_sign_result: dict[str, dict | str] = {}
    for user in await select_all_users(session):
        characters = await get_endfield_characters(user, session)
        for character in characters:
            sign_result[character.nickname] = await _endfield_sign_in(
                user, str(character.uid), character.channel_master_id
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
