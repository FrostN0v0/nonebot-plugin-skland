from nonebot_plugin_orm import async_scoped_session

from .schemas import CRED
from .api import SklandAPI
from .model import User, Character


async def get_characters_and_bind(user: User, session: async_scoped_session):
    cred = CRED(cred=user.cred, token=user.cred_token)
    binding_app_list = await SklandAPI.get_binding(cred)
    for app in binding_app_list:
        for character in app["bindingList"]:
            character_model = Character(
                id=user.id,
                uid=character["uid"],
                nickname=character["nickName"],
                app_code=app["appCode"],
                channel_master_id=character["channelMasterId"],
            )
        session.add(character_model)
    await session.commit()
