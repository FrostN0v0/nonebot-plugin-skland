"""卫戍协议概览、收藏和单局详情。"""

from nonebot.adapters import Bot
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, CustomNode, UniMessage

from ..exception import SklandException
from .selection import check_user_character
from ..render import render_garrison_history
from ..schemas.arknights.garrison import GarrisonView
from ..utils.message import send_reaction, send_request_error
from ..services.garrison import (
    fetch_garrison,
    get_garrison_teammates,
    archive_garrison_matches,
    get_archived_garrison_stats,
)

_FORWARD_IMAGE_LIMIT = 16


async def garrison_handler(
    user_session: UserSession,
    session: async_scoped_session,
    target: Match[At | int],
    bot: Bot,
    *,
    role_index: int | None = None,
    record_index: int | None = None,
    favored: bool = False,
    show_all: bool = False,
) -> None:
    if target.available:
        platform_id = target.result.target if isinstance(target.result, At) else target.result
        owner_id = (await get_user(user_session.platform, str(platform_id))).id
    else:
        owner_id = user_session.user_id
    selected = await check_user_character(owner_id, user_session, session, app_code="arknights", role_index=role_index)
    if selected is None:
        return
    user, character = selected
    character_id = character.id
    uid = str(character.uid)
    server_name = character.server_name
    channel_master_id = character.channel_master_id
    send_reaction(user_session, "processing")

    try:
        data, resources, resolved_activity = await fetch_garrison(user, uid)
    except SklandException as error:
        await session.commit()
        await send_request_error(error)
        return
    except ValueError as error:
        await session.commit()
        await UniMessage(str(error)).send(at_sender=True)
        return
    await archive_garrison_matches(session, character_id, resolved_activity, data)

    archived_stats = None
    teammates = []
    try:
        if record_index is None:
            archived_stats = await get_archived_garrison_stats(
                session, character_id, resolved_activity, data.history.records
            )
        else:
            records = data.history.favourRecords if favored else data.history.records
            if 1 <= record_index <= len(records):
                teammates = await get_garrison_teammates(
                    session, records[record_index - 1], resources, channel_master_id=channel_master_id, uid=uid
                )
    finally:
        await session.rollback()

    try:
        view = GarrisonView.from_data(
            data,
            resources,
            uid=uid,
            server_name=server_name,
            channel_master_id=channel_master_id,
            activity_id=resolved_activity,
            record_index=record_index,
            favored=favored,
            archived_stats=archived_stats,
            teammates=teammates,
        )
    except ValueError as error:
        await UniMessage(str(error)).send(at_sender=True)
        return

    images = await render_garrison_history(view, show_all=show_all)
    if len(images) > 1 and user_session.platform == "QQClient":
        for start in range(0, len(images), _FORWARD_IMAGE_LIMIT):
            nodes = [
                CustomNode(
                    bot.self_id,
                    f"{view.nickname} | 卫戍战绩 {index + 1}/{len(images)}",
                    UniMessage.image(raw=image),
                )
                for index, image in enumerate(images[start : start + _FORWARD_IMAGE_LIMIT], start=start)
            ]
            await UniMessage.reference(*nodes).send(reply_to=start == 0)
    else:
        for index, image in enumerate(images):
            await UniMessage.image(raw=image).send(reply_to=index == 0)
    send_reaction(user_session, "done")
