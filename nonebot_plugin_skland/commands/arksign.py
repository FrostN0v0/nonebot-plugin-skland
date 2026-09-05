"""Arknights Skland sign commands."""

import json
from datetime import datetime

from nonebot.adapters import Bot
from nonebot.params import Depends
from nonebot.compat import model_dump
from nonebot.permission import SuperUser
from nonebot_plugin_user import UserSession
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_alconna import Match, Arparma, CustomNode, UniMessage

from ..api import SklandAPI
from ..config import CACHE_DIR
from ..model import SkUser, Character
from .card import check_user_character
from ..schemas import CRED, ArkSignResponse
from .char import send_bound_roles_overview
from ..db_handler import (
    get_accounts,
    get_user_characters,
    select_all_accounts,
    get_account_characters,
    get_characters_by_role_id,
)
from ..utils import (
    send_reaction,
    format_sign_result,
    refresh_cred_token_if_needed,
    refresh_access_token_if_needed,
    refresh_cred_token_with_error_return,
    refresh_access_token_with_error_return,
)


def _role_title(character: Character) -> str:
    return f"{character.nickname} | {character.server_name} | {character.role_id}"


async def _select_characters(
    user_session: UserSession,
    session: async_scoped_session,
    uid: Match[str],
    result: Arparma,
) -> list[Character] | None:
    owner_id = user_session.user_id
    if uid.available:
        characters = await get_characters_by_role_id(
            owner_id,
            "arknights",
            uid.result,
            session,
        )
        if len(characters) != 1:
            await session.rollback()
            await send_bound_roles_overview(
                owner_id,
                user_session,
                session,
                text="未找到该角色标识" if not characters else "角色标识不唯一",
            )
            return None
        return characters
    if result.find("arksign.sign.all"):
        characters = await get_user_characters(owner_id, "arknights", session)
        if not characters:
            await session.rollback()
            await send_bound_roles_overview(
                owner_id,
                user_session,
                session,
                text="当前没有可签到的明日方舟角色",
            )
            return None
        return characters
    selected = await check_user_character(owner_id, user_session, session)
    return [selected[1]] if selected is not None else None


async def arksign_sign_handler(
    user_session: UserSession,
    session: async_scoped_session,
    uid: Match[str],
    result: Arparma,
) -> None:
    """Sign selected Arknights roles."""

    @refresh_cred_token_if_needed
    @refresh_access_token_if_needed
    async def sign_in(user: SkUser, character: Character):
        cred = CRED(cred=user.cred, token=user.cred_token)
        return await SklandAPI.ark_sign(
            cred,
            character.uid,
            channel_master_id=character.channel_master_id,
        )

    characters = await _select_characters(user_session, session, uid, result)
    if not characters:
        return
    send_reaction(user_session, "processing")

    messages: list[str] = []
    for character in characters:
        response = await sign_in(character.account, character)
        if response is not None:
            awards = "\n".join(f"{award.resource.name} x {award.count}" for award in response.awards)
            messages.append(f"角色: {_role_title(character)} 签到成功，获得了:\n{awards}")
    await session.commit()
    if messages:
        send_reaction(user_session, "done")
        await UniMessage("\n".join(messages)).send(at_sender=True)


@refresh_cred_token_with_error_return
@refresh_access_token_with_error_return
async def sign_in(user: SkUser, character: Character) -> ArkSignResponse:
    """Sign one Arknights role and return errors as strings."""
    cred = CRED(cred=user.cred, token=user.cred_token)
    return await SklandAPI.ark_sign(
        cred,
        character.uid,
        channel_master_id=character.channel_master_id,
    )


def _cache_entry(user: SkUser, character: Character, result: ArkSignResponse | str) -> dict:
    return {
        "owner_id": user.owner_id,
        "character_id": character.id,
        "nickname": character.nickname,
        "role_id": character.role_id,
        "server_id": character.channel_master_id,
        "server_name": character.server_name,
        "result": model_dump(result) if isinstance(result, ArkSignResponse) else result,
    }


async def arksign_status_handler(
    user_session: UserSession,
    session: async_scoped_session,
    bot: Bot,
    result: Arparma | bool,
    is_superuser: bool = Depends(SuperUser()),
) -> None:
    """Show cached Arknights sign results."""
    sign_result_file = CACHE_DIR / "sign_result.json"
    if not sign_result_file.exists():
        await UniMessage.text("未找到签到结果").send()
        return
    with open(sign_result_file, encoding="utf-8") as file:
        sign_result = json.load(file)
    sign_data = sign_result.get("data", [])
    if not isinstance(sign_data, list):
        await UniMessage("签到结果格式已更新,请等待下一次自动签到或重新执行全体签到").send(at_sender=True)
        return
    sign_time = sign_result.get("timestamp", "未记录签到时间")

    show_all = (isinstance(result, Arparma) and result.find("arksign.status.all")) or (
        isinstance(result, bool) and result
    )
    if show_all:
        if not is_superuser:
            await UniMessage.text("该指令仅超管可用").send()
            return
    else:
        accounts = await get_accounts(user_session.user_id, session)
        if not accounts:
            await session.rollback()
            await UniMessage("你还没有绑定森空岛账号").send(at_sender=True)
            return
        character_ids = {
            character.id for character in await get_user_characters(user_session.user_id, "arknights", session)
        }
        sign_data = [
            entry
            for entry in sign_data
            if entry.get("owner_id") == user_session.user_id and entry.get("character_id") in character_ids
        ]
        await session.rollback()

    send_reaction(user_session, "processing")
    if user_session.platform == "QQClient":
        parsed = format_sign_result(sign_data, sign_time, False)
        node_slice_limit = 98
        for offset in range(0, len(parsed.results), node_slice_limit):
            node_items = parsed.results[offset : offset + node_slice_limit]
            nodes = [CustomNode(bot.self_id, title, f"{content}\n") for title, content in node_items]
            if offset == 0:
                nodes.insert(0, CustomNode(bot.self_id, "签到结果", parsed.summary))
            await UniMessage.reference(*nodes).send()
    else:
        parsed = format_sign_result(sign_data, sign_time, True)
        formatted_messages = "\n".join(content for _title, content in parsed.results)
        await UniMessage.text(f"{parsed.summary}\n{formatted_messages}").send()
    send_reaction(user_session, "done")


async def arksign_all_handler(
    user_session: UserSession,
    session: async_scoped_session,
    bot: Bot,
    is_superuser: bool = Depends(SuperUser()),
) -> None:
    """Sign every persisted Arknights role."""
    if not is_superuser:
        await UniMessage.text("该指令仅超管可用").send()
        return
    send_reaction(user_session, "processing")
    entries: list[dict] = []
    for account in await select_all_accounts(session):
        for character in await get_account_characters(account.id, session):
            if character.app_code != "arknights":
                continue
            response = await sign_in(account, character)
            entries.append(_cache_entry(account, character, response))
    await session.commit()

    sign_result_file = CACHE_DIR / "sign_result.json"
    sign_result_file.parent.mkdir(parents=True, exist_ok=True)
    with open(sign_result_file, "w", encoding="utf-8") as file:
        json.dump(
            {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "data": entries},
            file,
            ensure_ascii=False,
            indent=2,
        )
    await arksign_status_handler(user_session, session, bot, True, is_superuser=is_superuser)
