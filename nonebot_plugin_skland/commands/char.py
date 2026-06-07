"""角色更新命令"""

from nonebot.params import Depends
from nonebot.permission import SuperUser
from nonebot_plugin_user import UserSession
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_alconna import Arparma, UniMessage

from ..db_handler import select_all_users
from ..utils import (
    bind_characters,
    get_characters_and_bind,
    refresh_cred_token_if_needed,
    refresh_access_token_if_needed,
    refresh_cred_token_with_error_return,
    refresh_access_token_with_error_return,
)


async def char_update_handler(
    user_session: UserSession, session: async_scoped_session, result: Arparma, is_superuser: bool = Depends(SuperUser())
):
    """更新森空岛角色信息"""

    if result.find("char.update.all"):
        if not is_superuser:
            await UniMessage.text("该指令仅超管可用").finish()
        await char_update_all_handler(session)
        return

    @refresh_cred_token_if_needed
    @refresh_access_token_if_needed
    async def refresh_characters(user):
        await get_characters_and_bind(user, session)
        await UniMessage("更新成功").send(at_sender=True)

    from ..model import SkUser

    if user := await session.get(SkUser, user_session.user_id):
        await refresh_characters(user)


async def char_update_all_handler(session: async_scoped_session):
    """更新所有绑定用户的角色信息"""

    @refresh_cred_token_with_error_return
    @refresh_access_token_with_error_return
    async def refresh_characters(user):
        await bind_characters(user, session)

    success_count = 0
    fail_count = 0
    users = await select_all_users(session)
    for user in users:
        result = await refresh_characters(user)
        if isinstance(result, str):
            fail_count += 1
        else:
            success_count += 1
    await session.commit()
    await UniMessage(f"全体角色更新完成\n成功: {success_count}, 失败: {fail_count}").send(at_sender=True)
