"""角色更新命令"""

from nonebot_plugin_user import UserSession
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_orm import async_scoped_session

from ..utils import get_characters_and_bind, refresh_cred_token_if_needed, refresh_access_token_if_needed


async def char_update_handler(user_session: UserSession, session: async_scoped_session):
    """更新森空岛角色信息"""

    @refresh_cred_token_if_needed
    @refresh_access_token_if_needed
    async def refresh_characters(user):
        await get_characters_and_bind(user, session)
        await UniMessage("更新成功").send(at_sender=True)

    from ..model import SkUser

    if user := await session.get(SkUser, user_session.user_id):
        await refresh_characters(user)
