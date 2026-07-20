"""干员盒 / 图鉴相关命令"""

from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, UniMessage

from ..api import SklandAPI
from ..schemas import CRED
from ..render import ROSTER_PAGE_WIDTH, render_operator_roster
from .card import check_user_character
from ..roster import (
    RosterFilter,
    build_box_cards,
    build_book_cards,
    filter_summary,
    parse_professions,
    parse_stars,
)
from ..utils import send_reaction, refresh_cred_token_if_needed, refresh_access_token_if_needed


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


async def box_handler(
    session: async_scoped_session,
    user_session: UserSession,
    target: Match[At | int],
    rarities: Match[str],
    professions: Match[str],
    name: Match[str],
):
    """明日方舟干员盒查询（仅已拥有）"""
    try:
        filt = _build_filter(rarities, professions, name)
    except ValueError as e:
        await UniMessage(str(e)).finish(at_sender=True)

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

    subtitle = (
        f"{info.status.name} · UID {info.status.uid} · "
        f"显示 {len(cards)} / 持有 {owned_n} · {summary} · 实装新→旧"
    )
    image = await render_operator_roster(
        title="Operator Box",
        subtitle=subtitle,
        cards=cards,
        page_width=ROSTER_PAGE_WIDTH,
    )
    send_reaction(user_session, "done")
    await UniMessage.image(raw=image).send(reply_to=True)
    await session.commit()


async def book_handler(
    session: async_scoped_session,
    user_session: UserSession,
    target: Match[At | int],
    rarities: Match[str],
    professions: Match[str],
    name: Match[str],
):
    """明日方舟干员图鉴查询（未拥有灰显）"""
    try:
        filt = _build_filter(rarities, professions, name)
    except ValueError as e:
        await UniMessage(str(e)).finish(at_sender=True)

    target_id = await _resolve_target_id(user_session, target)
    user, ark_character = await check_user_character(target_id, session)
    send_reaction(user_session, "processing")

    info = await _fetch_ark_card(user, str(ark_character.uid))
    if not info:
        return

    cards = build_book_cards(info.chars, filt, equipment_map=info.equipmentInfoMap)
    owned_shown = sum(1 for c in cards if c.owned)
    summary = filter_summary(filt)
    if not cards:
        send_reaction(user_session, "done")
        await UniMessage(f"没有匹配的干员 · {summary}").finish(at_sender=True)

    subtitle = (
        f"{info.status.name} · UID {info.status.uid} · "
        f"显示 {len(cards)}（已拥有 {owned_shown}）· {summary} · 实装新→旧"
    )
    image = await render_operator_roster(
        title="Operator Book",
        subtitle=subtitle,
        cards=cards,
        page_width=ROSTER_PAGE_WIDTH,
    )
    send_reaction(user_session, "done")
    await UniMessage.image(raw=image).send(reply_to=True)
    await session.commit()
