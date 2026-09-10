from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import At, Match, UniMessage

from ...api import SklandAPI
from ...model import SkUser, Character
from ...exception import SklandException
from ...render import render_ef_war_echoes
from ...schemas import CRED, WarEchoesView
from ..selection import check_user_character
from ...services.auth import refresh_credentials
from ...utils.message import send_reaction, send_request_error


async def ef_war_echoes_handler(
    user_session: UserSession,
    session: async_scoped_session,
    target: Match[At | int],
    *,
    role_index: int | None = None,
    season_id: int | None = None,
    week_id: int | None = None,
) -> None:
    @refresh_credentials
    async def get_war_echoes(user: SkUser, character: Character, user_id: str, requested_season_id: int | str | None):
        return await SklandAPI.endfield_war_echoes(
            CRED(cred=user.cred, token=user.cred_token),
            user_id=user_id,
            role_id=character.role_id,
            server_id=character.channel_master_id,
            season_id=requested_season_id,
        )

    if target.available:
        platform_id = target.result.target if isinstance(target.result, At) else target.result
        owner_id = (await get_user(user_session.platform, str(platform_id))).id
    else:
        owner_id = user_session.user_id

    selected = await check_user_character(owner_id, user_session, session, app_code="endfield", role_index=role_index)
    if selected is None:
        return
    user, character = selected
    if not user.skland_user_id:
        await session.rollback()
        await UniMessage("账号身份尚未同步,请先执行 sk char update").send(at_sender=True)
        return

    send_reaction(user_session, "processing")
    resolved_season_id: str | int | None = season_id
    try:
        requested_season_id = None if season_id is not None and season_id < 0 else season_id
        data = await get_war_echoes(user, character, user.skland_user_id, requested_season_id)
        if season_id is not None and season_id < 0:
            resolved_season_id = data.select_season(season_id).id
            data = await get_war_echoes(user, character, user.skland_user_id, resolved_season_id)
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
        view = WarEchoesView.from_data(data, season_id=resolved_season_id, week_id=week_id)
    except ValueError as error:
        await UniMessage(str(error)).send(at_sender=True)
        return

    image = await render_ef_war_echoes(view)
    send_reaction(user_session, "done")
    await UniMessage.image(raw=image).send(reply_to=True)
