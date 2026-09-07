from nonebot_plugin_user import UserSession
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_orm import async_scoped_session

from ...model import SkUser, Character
from ..char import send_bound_roles_overview
from ...db_handler import get_accounts, get_default_character, get_character_by_index


async def check_user_character(
    owner_id: int,
    user_session: UserSession,
    session: async_scoped_session,
    *,
    role_index: int | None = None,
) -> tuple[SkUser, Character] | None:
    """Resolve the owner's selected Endfield role and its account."""
    requester_owner_id = user_session.user_id
    if role_index is not None:
        if owner_id != requester_owner_id:
            await session.rollback()
            await UniMessage("不能为其他用户指定角色").send(at_sender=True)
            return None
        character = await get_character_by_index(owner_id, "endfield", role_index, session)
        if character is not None:
            return character.account, character
        await session.rollback()
        await send_bound_roles_overview(
            owner_id,
            user_session,
            session,
            text="角色序号无效,请以最新 sk char 卡片为准",
        )
        return None

    character = await get_default_character(owner_id, "endfield", session)
    if character is not None:
        return character.account, character

    has_accounts = bool(await get_accounts(owner_id, session))
    await session.rollback()
    if owner_id != requester_owner_id:
        await UniMessage("目标用户尚未设置终末地默认角色").send(at_sender=True)
    elif has_accounts:
        await send_bound_roles_overview(
            owner_id,
            user_session,
            session,
            text="当前尚未设置终末地默认角色,请执行 sk char set ef <序号>",
        )
    else:
        await UniMessage("你还没有绑定森空岛账号").send(at_sender=True)
    return None
