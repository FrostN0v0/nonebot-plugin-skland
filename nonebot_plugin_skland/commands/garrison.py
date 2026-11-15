"""卫戍协议概览、收藏和单局详情。"""

from nonebot.adapters import Bot
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, CustomNode, UniMessage

from ..exception import SklandException
from .selection import check_user_character
from ..render import render_garrison_history
from ..services.garrison import fetch_garrison
from ..schemas.arknights.garrison import GarrisonView
from ..utils.message import send_reaction, send_request_error


async def garrison_handler(
    user_session: UserSession,
    session: async_scoped_session,
    target: Match[At | int],
    bot: Bot,
    *,
    role_index: int | None = None,
    record_index: int | None = None,
    favored: bool = False,
    activity_id: str | None = None,
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
    uid = str(character.uid)
    server_name = character.server_name
    send_reaction(user_session, "processing")

    try:
        data, resources, resolved_activity = await fetch_garrison(user, uid, activity_id=activity_id)
    except SklandException as error:
        await session.commit()
        await send_request_error(error)
        return
    except ValueError as error:
        await session.commit()
        await UniMessage(str(error)).send(at_sender=True)
        return
    await session.commit()

    try:
        view = GarrisonView.from_data(
            data,
            resources,
            uid=uid,
            server_name=server_name,
            activity_id=resolved_activity,
            record_index=record_index,
            favored=favored,
        )
    except ValueError as error:
        await UniMessage(str(error)).send(at_sender=True)
        return

    images = await render_garrison_history(view)
    if len(images) > 1 and user_session.platform == "QQClient":
        nodes = [
            CustomNode(
                bot.self_id,
                f"{view.nickname} | 卫戍战绩 {index + 1}/{len(images)}",
                UniMessage.image(raw=image),
            )
            for index, image in enumerate(images)
        ]
        await UniMessage.reference(*nodes).send(reply_to=True)
    else:
        for index, image in enumerate(images):
            await UniMessage.image(raw=image).send(reply_to=index == 0)
    send_reaction(user_session, "done")
