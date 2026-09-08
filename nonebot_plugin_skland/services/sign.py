"""Sign execution, persisted results, and game-aware presentation."""

import json
from pathlib import Path
from datetime import datetime

from nonebot.compat import model_dump
from nonebot_plugin_orm import async_scoped_session

from ..api import SklandAPI
from ..config import CACHE_DIR
from ..model import SkUser, Character
from .auth import refresh_credentials
from ..exception import SklandException, SignCacheFormatError
from ..db_handler import select_all_accounts, get_account_characters
from ..schemas import CRED, SignGame, SignCache, SignResult, SignCacheEntry, ArkSignResponse, EndfieldSignResponse


@refresh_credentials
async def ark_sign_in(user: SkUser, character: Character) -> ArkSignResponse:
    return await SklandAPI.ark_sign(
        CRED(cred=user.cred, token=user.cred_token),
        character.uid,
        channel_master_id=character.channel_master_id,
    )


@refresh_credentials
async def endfield_sign_in(user: SkUser, character: Character) -> EndfieldSignResponse:
    return await SklandAPI.endfield_sign(
        CRED(cred=user.cred, token=user.cred_token),
        character.role_id,
        server_id=character.channel_master_id,
    )


async def sign_character(user: SkUser, character: Character, game: SignGame) -> SignCacheEntry:
    """Record a role outcome, converting API errors only at the sign boundary."""
    try:
        response = (
            await ark_sign_in(user, character) if game == "arknights" else await endfield_sign_in(user, character)
        )
        result = model_dump(response)
    except SklandException as error:
        result = f"接口请求失败,{error.args[0]}"
    return {
        "owner_id": user.owner_id,
        "character_id": character.id,
        "nickname": character.nickname,
        "role_id": character.role_id,
        "server_id": character.channel_master_id,
        "server_name": character.server_name,
        "result": result,
    }


async def sign_all_characters(session: async_scoped_session, game: SignGame) -> list[SignCacheEntry]:
    """Sign in database order without committing the caller's transaction."""
    entries: list[SignCacheEntry] = []
    for account in await select_all_accounts(session):
        for character in await get_account_characters(account.id, session):
            if character.app_code == game:
                entries.append(await sign_character(account, character, game))
    return entries


def _cache_path(game: SignGame) -> Path:
    return CACHE_DIR / ("sign_result.json" if game == "arknights" else "endfield_sign_result.json")


def write_sign_cache(game: SignGame, entries: list[SignCacheEntry]) -> None:
    path = _cache_path(game)
    path.parent.mkdir(parents=True, exist_ok=True)
    cache: SignCache = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "data": entries}
    with path.open("w", encoding="utf-8") as file:
        json.dump(cache, file, ensure_ascii=False, indent=2)


def read_sign_cache(game: SignGame) -> SignCache | None:
    path = _cache_path(game)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as file:
        cache = json.load(file)
    entries = cache.get("data", [])
    if not isinstance(entries, list):
        raise SignCacheFormatError("签到结果格式已更新,请等待下一次自动签到或重新执行全体签到")
    return {"timestamp": cache.get("timestamp", "未记录签到时间"), "data": entries}


def filter_sign_cache(cache: SignCache, *, owner_id: int | None, character_ids: set[int] | None) -> SignCache:
    if character_ids is None:
        return cache
    return {
        "timestamp": cache["timestamp"],
        "data": [
            entry
            for entry in cache["data"]
            if entry.get("owner_id") == owner_id and entry.get("character_id") in character_ids
        ],
    }


def _sign_entry_title(entry: SignCacheEntry) -> str:
    return f"{entry['nickname']} | {entry['server_name']} | {entry['role_id']}"


def _format_sign_result(sign_data: list[SignCacheEntry], sign_time: str, is_text: bool, game: SignGame) -> SignResult:
    formatted_results: list[tuple[str, str]] = []
    success_count = 0
    failed_count = 0
    for entry in sign_data:
        title = _sign_entry_title(entry)
        result_data = entry["result"]
        if isinstance(result_data, dict):
            if game == "arknights":
                awards_text = "\n".join(
                    f"  {award['resource']['name']} x {award['count']}" for award in result_data["awards"]
                )
            else:
                resource_info_map = result_data.get("resourceInfoMap", {})
                award_lines = []
                for award in result_data.get("awardIds", []):
                    info = resource_info_map.get(award["id"], {})
                    award_lines.append(f"  {info.get('name', '未知物品')} x{info.get('count', 0)}")
                awards_text = "\n".join(award_lines)
            content = (
                f"✅ 角色：{title} 签到成功，获得了:\n📦{awards_text}"
                if is_text
                else f"✅ 签到成功，获得了:\n📦{awards_text}"
            )
            success_count += 1
        elif "请勿重复签到" in result_data:
            content = f"ℹ️ 角色：{title} 已签到 (无需重复签到)" if is_text else "ℹ️ 已签到 (无需重复签到)"
            success_count += 1
        else:
            content = f"❌ 角色：{title} 签到失败: {result_data}" if is_text else f"❌ 签到失败: {result_data}"
            failed_count += 1
        formatted_results.append((title, content))
    heading = "签到结果概览" if game == "arknights" else "终末地签到结果概览"
    return SignResult(
        failed_count=failed_count,
        success_count=success_count,
        results=formatted_results,
        summary=(
            f"--- {heading} ---\n"
            f"总计签到角色: {len(formatted_results)}个\n"
            f"✅ 成功签到: {success_count}个\n"
            f"❌ 签到失败: {failed_count}个\n"
            f"⏰️ 签到时间: {sign_time}\n"
            f"--------------------"
        ),
    )


def format_sign_result(sign_data: list[SignCacheEntry], sign_time: str, is_text: bool) -> SignResult:
    """Format ordered Arknights sign cache entries."""
    return _format_sign_result(sign_data, sign_time, is_text, "arknights")


def format_endfield_sign_result(sign_data: list[SignCacheEntry], sign_time: str, is_text: bool) -> SignResult:
    """Format ordered Endfield sign cache entries."""
    return _format_sign_result(sign_data, sign_time, is_text, "endfield")
