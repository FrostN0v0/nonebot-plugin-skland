"""Operator roster commands."""

import asyncio

from nonebot.adapters import Bot
from pydantic import AnyUrl as Url
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, CustomNode, UniMessage

from ..api import SklandAPI
from ..config import config
from .card import check_user_character
from ..exception import RequestException
from ..data_source import gacha_table_data
from ..render import render_operator_roster
from ..schemas import CRED, OperatorCard, OperatorFilter, OperatorRoster
from ..utils import (
    send_reaction,
    get_background_image,
    refresh_cred_token_if_needed,
    refresh_access_token_if_needed,
)


async def _resolve_target_id(user_session: UserSession, target: Match[At | int]) -> int:
    if target.available:
        target_platform_id = target.result.target if isinstance(target.result, At) else target.result
        return (await get_user(user_session.platform, str(target_platform_id))).id
    return user_session.user_id


def _match_value(match: Match[str]) -> str | None:
    return match.result if match.available else None


def _build_filter(
    rarities: Match[str],
    professions: Match[str],
    branches: Match[str],
    positions: Match[str],
    genders: Match[str],
    factions: Match[str],
    races: Match[str],
    name: Match[str],
) -> OperatorFilter:
    return OperatorFilter.from_raw(
        gacha_table_data.operator_catalog,
        rarities=_match_value(rarities),
        professions=_match_value(professions),
        branches=_match_value(branches),
        positions=_match_value(positions),
        genders=_match_value(genders),
        factions=_match_value(factions),
        races=_match_value(races),
        name=_match_value(name),
    )


@refresh_cred_token_if_needed
@refresh_access_token_if_needed
async def _fetch_ark_card(user, uid: str):
    return await SklandAPI.ark_card(CRED(cred=user.cred, token=user.cred_token), uid)


async def _get_roster_background_image() -> str | Url | None:
    if config.background_source == "default":
        return None
    return await get_background_image("ark")


def _split_roster_cards(cards: list[OperatorCard], page_size: int) -> list[list[OperatorCard]]:
    return [cards[index : index + page_size] for index in range(0, len(cards), page_size)]


async def _render_roster_pages(
    *,
    roster: OperatorRoster,
    background_image: str | Url | None,
    page_size: int,
) -> list[bytes]:
    semaphore = asyncio.Semaphore(4)

    async def render(page_cards: list[OperatorCard]) -> bytes:
        async with semaphore:
            return await render_operator_roster(
                props=roster.with_cards(page_cards),
                background_image=background_image,
            )

    return await asyncio.gather(*(render(page) for page in _split_roster_cards(roster.cards, page_size)))


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
    roster: OperatorRoster,
    background_image: str | Url | None,
    user_session: UserSession,
    bot: Bot,
) -> None:
    page_size = config.roster_render_max
    images = await _render_roster_pages(
        roster=roster,
        background_image=background_image,
        page_size=page_size,
    )
    await _send_roster_images(
        images=images,
        total_cards=len(roster.cards),
        page_size=page_size,
        status_name=roster.status.name,
        user_session=user_session,
        bot=bot,
    )


async def box_handler(
    session: async_scoped_session,
    user_session: UserSession,
    target: Match[At | int],
    rarities: Match[str],
    professions: Match[str],
    branches: Match[str],
    positions: Match[str],
    genders: Match[str],
    factions: Match[str],
    races: Match[str],
    name: Match[str],
    bot: Bot,
    *,
    book: bool = False,
):
    """Query an owned operator box or the complete operator book."""
    if not gacha_table_data.operator_catalog.entries:
        try:
            gacha_table_data.load_operator_catalog()
        except RequestException as e:
            await UniMessage.text(str(e)).finish(at_sender=True)
            return

    try:
        operator_filter = _build_filter(
            rarities,
            professions,
            branches,
            positions,
            genders,
            factions,
            races,
            name,
        )
    except ValueError as e:
        await UniMessage.text(str(e)).finish(at_sender=True)
        return

    target_id = await _resolve_target_id(user_session, target)
    user, ark_character = await check_user_character(target_id, session)
    send_reaction(user_session, "processing")

    info = await _fetch_ark_card(user, str(ark_character.uid))
    if not info:
        return

    roster = OperatorRoster.build(
        status=info.status,
        catalog=gacha_table_data.operator_catalog,
        characters=info.chars,
        operator_filter=operator_filter,
        equipment_map=info.equipmentInfoMap,
        book=book,
    )
    if not roster.cards:
        send_reaction(user_session, "done")
        owned_summary = f"（持有 {len(info.chars)}）" if not book else ""
        await UniMessage.text(f"没有匹配的干员{owned_summary} · {roster.summary}").finish(at_sender=True)
        return

    background = await _get_roster_background_image()
    await _render_and_send_roster(
        roster=roster,
        background_image=background,
        user_session=user_session,
        bot=bot,
    )
    send_reaction(user_session, "done")
    await session.commit()
