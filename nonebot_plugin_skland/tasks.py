"""Scheduled Skland sign tasks."""

import json
from datetime import datetime

from nonebot.compat import model_dump
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_orm import get_scoped_session

from .api import SklandAPI
from .config import CACHE_DIR
from .model import SkUser, Character
from .schemas import CRED, ArkSignResponse, EndfieldSignResponse
from .db_handler import select_all_accounts, get_account_characters
from .utils import refresh_cred_token_with_error_return, refresh_access_token_with_error_return


@refresh_cred_token_with_error_return
@refresh_access_token_with_error_return
async def _ark_sign_in(user: SkUser, character: Character) -> ArkSignResponse:
    cred = CRED(cred=user.cred, token=user.cred_token)
    return await SklandAPI.ark_sign(
        cred,
        character.uid,
        channel_master_id=character.channel_master_id,
    )


@refresh_cred_token_with_error_return
@refresh_access_token_with_error_return
async def _endfield_sign_in(user: SkUser, character: Character) -> EndfieldSignResponse:
    cred = CRED(cred=user.cred, token=user.cred_token)
    return await SklandAPI.endfield_sign(
        cred,
        character.role_id,
        server_id=character.channel_master_id,
    )


def _cache_entry(user: SkUser, character: Character, result: ArkSignResponse | EndfieldSignResponse | str) -> dict:
    return {
        "owner_id": user.owner_id,
        "character_id": character.id,
        "nickname": character.nickname,
        "role_id": character.role_id,
        "server_id": character.channel_master_id,
        "server_name": character.server_name,
        "result": model_dump(result) if isinstance(result, (ArkSignResponse, EndfieldSignResponse)) else result,
    }


def _write_sign_cache(filename: str, entries: list[dict]) -> None:
    result_file = CACHE_DIR / filename
    result_file.parent.mkdir(parents=True, exist_ok=True)
    with open(result_file, "w", encoding="utf-8") as file:
        json.dump(
            {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "data": entries},
            file,
            ensure_ascii=False,
            indent=2,
        )


@scheduler.scheduled_job("cron", hour=0, minute=15, id="daily_arksign")
async def run_daily_arksign() -> None:
    """Run the daily Arknights sign task."""
    session = get_scoped_session()
    try:
        entries: list[dict] = []
        for account in await select_all_accounts(session):
            for character in await get_account_characters(account.id, session):
                if character.app_code != "arknights":
                    continue
                result = await _ark_sign_in(account, character)
                entries.append(_cache_entry(account, character, result))
        await session.commit()
        _write_sign_cache("sign_result.json", entries)
    finally:
        await session.close()


@scheduler.scheduled_job("cron", hour=0, minute=20, id="daily_efsign")
async def run_daily_efsign() -> None:
    """Run the daily Endfield sign task."""
    session = get_scoped_session()
    try:
        entries: list[dict] = []
        for account in await select_all_accounts(session):
            for character in await get_account_characters(account.id, session):
                if character.app_code != "endfield":
                    continue
                result = await _endfield_sign_in(account, character)
                entries.append(_cache_entry(account, character, result))
        await session.commit()
        _write_sign_cache("endfield_sign_result.json", entries)
    finally:
        await session.close()
