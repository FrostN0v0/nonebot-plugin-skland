from datetime import datetime

from nonebot.log import logger
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_orm import async_scoped_session

from nonebot_plugin_skland.schemas.ark_models.assist_chars import AssistChar

from .schemas import CRED
from .config import CACHE_DIR
from .model import User, Character
from .db_handler import delete_characters
from .api import SklandAPI, SklandLoginAPI
from .exception import LoginException, RequestException, UnauthorizedException


async def get_characters_and_bind(user: User, session: async_scoped_session):
    await delete_characters(user, session)

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
                isdefault=character["isDefault"],
            )
            if len(app["bindingList"]) == 1:
                character_model.isdefault = True
            session.add(character_model)
    await session.commit()


def refresh_access_token_if_needed(func):
    """装饰器：如果 access_token 失效，刷新后重试"""

    async def wrapper(user: User, *args, **kwargs):
        try:
            return await func(user, *args, **kwargs)
        except LoginException:
            if not user.access_token:
                await UniMessage("cred失效，用户没有绑定token，无法自动刷新cred").send(at_sender=True)

            try:
                grant_code = await SklandLoginAPI.get_grant_code(user.access_token)
                new_cred = await SklandLoginAPI.get_cred(grant_code)
                user.cred, user.cred_token = new_cred.cred, new_cred.token
                logger.info("access_token 失效，已自动刷新")
                return await func(user, *args, **kwargs)
            except (RequestException, LoginException, UnauthorizedException) as e:
                await UniMessage(f"接口请求失败,错误信息:{e}").send(at_sender=True)
        except RequestException as e:
            await UniMessage(f"接口请求失败,错误信息:{e}").send(at_sender=True)

    return wrapper


def refresh_cred_token_if_needed(func):
    """装饰器：如果 cred_token 失效，刷新后重试"""

    async def wrapper(user: User, *args, **kwargs):
        try:
            return await func(user, *args, **kwargs)
        except UnauthorizedException:
            try:
                new_token = await SklandLoginAPI.refresh_token(user.cred)
                user.cred_token = new_token
                logger.info("cred_token 失效，已自动刷新")
                return await func(user, *args, **kwargs)
            except (RequestException, LoginException, UnauthorizedException) as e:
                await UniMessage(f"接口请求失败,错误信息:{e}").send(at_sender=True)
        except RequestException as e:
            await UniMessage(f"接口请求失败,错误信息:{e}").send(at_sender=True)

    return wrapper


def format_time_from_timestamp(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")


def get_portrait(char: AssistChar) -> str:
    for symbol in ["@", "#"]:
        if symbol in char.skinId:
            portrait_id = char.skinId.replace(symbol, "_", 1)
            break
    img_path = CACHE_DIR / "portrait" / f"{portrait_id}.png"
    return img_path.as_uri()
