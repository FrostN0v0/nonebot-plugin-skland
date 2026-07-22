"""Operator roster commands."""

import asyncio

from nonebot.adapters import Bot
from pydantic import AnyUrl as Url
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, CustomNode, UniMessage

from ..api import SklandAPI
from ..config import config
from ..schemas import CRED, Status
from .card import check_user_character
from ..render import render_operator_roster
from ..utils import (
    send_reaction,
    get_background_image,
    refresh_cred_token_if_needed,
    refresh_access_token_if_needed,
)
from ..roster import (
    RosterCard,
    RosterFilter,
    filter_tags,
    parse_stars,
    filter_summary,
    build_box_cards,
    build_book_cards,
    parse_professions,
)


async def _resolve_target_id(user_session: UserSession, target: Match[At | int]) -> int:
    if target.available:
        target_platform_id = target.result.target if isinstance(target.result, At) else target.result
        return (await get_user(user_session.platform, str(target_platform_id))).id
    return user_session.user_id


def _build_filter(rarities: Match[str], professions: Match[str], name: Match[str]) -> RosterFilter:
    return RosterFilter(
        stars=parse_stars(rarities.result if rarities.available else None),
        professions=parse_professions(professions.result if professions.available else None),
        name=(name.result.strip() if name.available and name.result else ""),
    )


@refresh_cred_token_if_needed
@refresh_access_token_if_needed
async def _fetch_ark_card(user, uid: str):
    return await SklandAPI.ark_card(CRED(cred=user.cred, token=user.cred_token), uid)


async def _get_roster_background_image() -> str | Url | None:
    if config.background_source == "default":
        return None
    return await get_background_image("ark")


def _split_roster_cards(cards: list[RosterCard], page_size: int) -> list[list[RosterCard]]:
    return [cards[index : index + page_size] for index in range(0, len(cards), page_size)]


async def _render_roster_pages(
    *,
    title: str,
    status: Status,
    tags: list[str],
    cards: list[RosterCard],
    background_image: str | Url | None,
    page_size: int,
) -> list[bytes]:
    semaphore = asyncio.Semaphore(4)

    async def render(page_cards: list[RosterCard]) -> bytes:
        async with semaphore:
            return await render_operator_roster(
                title=title,
                status=status,
                tags=tags,
                cards=page_cards,
                background_image=background_image,
            )

    return await asyncio.gather(*(render(page) for page in _split_roster_cards(cards, page_size)))


async def _send_roster_images(
    *,
    images: list[bytes],
    total_cards: int,
    page_size: int,
    status_name: str,
    user_session: UserSession,
    bot: Bot,
) -> None:
    if len(images) == 1:
        await UniMessage.image(raw=images[0]).send(reply_to=True)
        return

    await UniMessage.text("干员数量过多，将以多张图片形式发送").send(reply_to=True)
    if user_session.platform == "QQClient":
        nodes = []
        for index, image in enumerate(images):
            start = index * page_size + 1
            end = min(start + page_size - 1, total_cards)
            nodes.append(
                CustomNode(
                    bot.self_id,
                    f"{status_name} | 干员 {start}-{end}",
                    UniMessage.image(raw=image),
                )
            )
        await UniMessage.reference(*nodes).send()
        return

    for image in images:
        await UniMessage.image(raw=image).send()


async def _render_and_send_roster(
    *,
    title: str,
    status: Status,
    tags: list[str],
    cards: list[RosterCard],
    background_image: str | Url | None,
    user_session: UserSession,
    bot: Bot,
) -> None:
    page_size = config.roster_render_max
    images = await _render_roster_pages(
        title=title,
        status=status,
        tags=tags,
        cards=cards,
        background_image=background_image,
        page_size=page_size,
    )
    await _send_roster_images(
        images=images,
        total_cards=len(cards),
        page_size=page_size,
        status_name=status.name,
        user_session=user_session,
        bot=bot,
    )


async def box_handler(
    session: async_scoped_session,
    user_session: UserSession,
    target: Match[At | int],
    rarities: Match[str],
    professions: Match[str],
    name: Match[str],
    bot: Bot,
):
    """明日方舟干员盒查询（仅已拥有）"""
    try:
        filt = _build_filter(rarities, professions, name)
    except ValueError as e:
        await UniMessage(str(e)).finish(at_sender=True)
        return

    target_id = await _resolve_target_id(user_session, target)
    user, ark_character = await check_user_character(target_id, session)
    send_reaction(user_session, "processing")

    info = await _fetch_ark_card(user, str(ark_character.uid))
    if not info:
        return

    cards = build_box_cards(info.chars, filt, equipment_map=info.equipmentInfoMap)
    owned_n = len(info.chars)
    summary = filter_summary(filt)
    if not cards:
        send_reaction(user_session, "done")
        await UniMessage(f"没有匹配的干员（持有 {owned_n}）· {summary}").finish(at_sender=True)
        return

    background = await _get_roster_background_image()
    await _render_and_send_roster(
        title="Operator Box",
        status=info.status,
        tags=filter_tags(filt),
        cards=cards,
        background_image=background,
        user_session=user_session,
        bot=bot,
    )
    send_reaction(user_session, "done")
    await session.commit()


async def book_handler(
    session: async_scoped_session,
    user_session: UserSession,
    target: Match[At | int],
    rarities: Match[str],
    professions: Match[str],
    name: Match[str],
    bot: Bot,
):
    """明日方舟干员图鉴查询（未拥有灰显）"""
    try:
        filt = _build_filter(rarities, professions, name)
    except ValueError as e:
        await UniMessage(str(e)).finish(at_sender=True)
        return

    target_id = await _resolve_target_id(user_session, target)
    user, ark_character = await check_user_character(target_id, session)
    send_reaction(user_session, "processing")

    info = await _fetch_ark_card(user, str(ark_character.uid))
    if not info:
        return

    cards = build_book_cards(info.chars, filt, equipment_map=info.equipmentInfoMap)
    summary = filter_summary(filt)
    if not cards:
        send_reaction(user_session, "done")
        await UniMessage(f"没有匹配的干员 · {summary}").finish(at_sender=True)
        return

    background = await _get_roster_background_image()
    await _render_and_send_roster(
        title="Operator Book",
        status=info.status,
        tags=filter_tags(filt),
        cards=cards,
        background_image=background,
        user_session=user_session,
        bot=bot,
    )
    send_reaction(user_session, "done")
    await session.commit()
