from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_orm import async_scoped_session

from ...model import SkUser, Character
from ...db_handler import get_default_endfield_character


async def check_user_character(user_id: int, session: async_scoped_session) -> tuple[SkUser, Character]:
    """检查用户和角色绑定状态"""
    user = await session.get(SkUser, user_id)
    if not user:
        await UniMessage("未绑定 skland 账号").finish(at_sender=True)
    char = await get_default_endfield_character(user, session)
    if not char:
        await UniMessage("未绑定 arknights 账号").finish(at_sender=True)
    return user, char
