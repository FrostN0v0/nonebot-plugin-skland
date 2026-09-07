"""Arknights Skland sign commands."""

from nonebot.adapters import Bot
from nonebot.params import Depends
from nonebot.permission import SuperUser
from nonebot_plugin_user import UserSession
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_alconna import Arparma, CustomNode, UniMessage

from ..model import Character
from ..db_handler import get_accounts, get_user_characters
from ..exception import SklandException, SignCacheFormatError
from ..utils.message import send_reaction, send_request_error
from .selection import check_user_character, send_bound_roles_overview
from ..services.sign import (
    ark_sign_in,
    read_sign_cache,
    write_sign_cache,
    filter_sign_cache,
    format_sign_result,
    sign_all_characters,
)


def _role_title(character: Character) -> str:
    return f"{character.nickname} | {character.server_name} | {character.role_id}"


async def _select_characters(
    user_session: UserSession,
    session: async_scoped_session,
    role_index: int | None,
    result: Arparma,
) -> list[Character] | None:
    owner_id = user_session.user_id
    show_all = result.find("arksign.sign.all")
    if role_index is not None and show_all:
        await session.rollback()
        await UniMessage("角色序号 (--role) 与全体签到 (--all) 不能同时使用").send(at_sender=True)
        return None
    if show_all:
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
    selected = await check_user_character(
        owner_id,
        user_session,
        session,
        app_code="arknights",
        role_index=role_index,
    )
    return [selected[1]] if selected is not None else None


async def arksign_sign_handler(
    user_session: UserSession,
    session: async_scoped_session,
    role_index: int | None,
    result: Arparma,
) -> None:
    """Sign selected Arknights roles."""
    characters = await _select_characters(user_session, session, role_index, result)
    if not characters:
        return
    send_reaction(user_session, "processing")

    messages: list[str] = []
    for character in characters:
        try:
            response = await ark_sign_in(character.account, character)
        except SklandException as error:
            await send_request_error(error)
        else:
            awards = "\n".join(f"{award.resource.name} x {award.count}" for award in response.awards)
            messages.append(f"角色: {_role_title(character)} 签到成功，获得了:\n{awards}")
    await session.commit()
    if messages:
        send_reaction(user_session, "done")
        await UniMessage("\n".join(messages)).send(at_sender=True)


async def arksign_status_handler(
    user_session: UserSession,
    session: async_scoped_session,
    bot: Bot,
    result: Arparma | bool,
    is_superuser: bool = Depends(SuperUser()),
    *,
    role_index: int | None = None,
) -> None:
    """Show cached Arknights sign results."""
    show_all = (isinstance(result, Arparma) and result.find("arksign.status.all")) or (
        isinstance(result, bool) and result
    )
    owner_id: int | None = None
    character_ids: set[int] | None = None
    if role_index is not None and show_all:
        await session.rollback()
        await UniMessage("角色序号 (-r/--role) 与全体状态 (--all) 不能同时使用").send(at_sender=True)
        return
    if show_all:
        if not is_superuser:
            await session.rollback()
            await UniMessage.text("该指令仅超管可用").send()
            return
    else:
        owner_id = user_session.user_id
        if role_index is not None:
            selected = await check_user_character(
                owner_id, user_session, session, app_code="arknights", role_index=role_index
            )
            if selected is None:
                return
            character_ids = {selected[1].id}
        else:
            accounts = await get_accounts(owner_id, session)
            if not accounts:
                await session.rollback()
                await UniMessage("你还没有绑定森空岛账号").send(at_sender=True)
                return
            character_ids = {character.id for character in await get_user_characters(owner_id, "arknights", session)}
    await session.rollback()

    try:
        cache = read_sign_cache("arknights")
    except SignCacheFormatError as error:
        await UniMessage(str(error)).send(at_sender=True)
        return
    if cache is None:
        await UniMessage.text("未找到签到结果").send()
        return
    cache = filter_sign_cache(cache, owner_id=owner_id, character_ids=character_ids)
    sign_data, sign_time = cache["data"], cache["timestamp"]
    if not sign_data:
        await UniMessage.text("未找到签到结果").send()
        return

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
    entries = await sign_all_characters(session, "arknights")
    await session.commit()

    write_sign_cache("arknights", entries)
    await arksign_status_handler(user_session, session, bot, True, is_superuser=is_superuser)
