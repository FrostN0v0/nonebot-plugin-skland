import httpx
from nonebot import logger
from pydantic import AnyUrl as Url
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_orm import async_scoped_session

from .schemas import CRED
from .model import User, Character
from .db_handler import delete_characters
from .api import SklandAPI, SklandLoginAPI
from .config import RES_DIR, CustomSource, config
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


async def get_lolicon_image() -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.lolicon.app/setu/v2?tag=arknights")
    return response.json()["data"][0]["urls"]["original"]


async def get_background_image() -> str | Url:
    default_background = RES_DIR / "images" / "background" / "bg.jpg"

    match config.background_source:
        case "default":
            background_image = default_background.as_posix()
        case "Lolicon":
            background_image = await get_lolicon_image()
        case "random":
            background_image = CustomSource(uri=RES_DIR / "images" / "background").to_uri()
        case CustomSource() as cs:
            background_image = cs.to_uri()
        case _:
            background_image = default_background.as_posix()

    return background_image
