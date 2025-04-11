from nonebot import logger, get_driver

from .config import config
from .exception import RequestException
from .download import GameResourceDownloader

driver = get_driver()

RESOURCE_ROUTES = ["portrait", "avatar", "skill"]


@driver.on_startup
async def startup():
    if config.check_res_update:
        try:
            if version := await GameResourceDownloader.check_update():
                logger.info("开始下载游戏资源")
                for route in RESOURCE_ROUTES:
                    logger.info(f"正在下载: {route}")
                    await GameResourceDownloader.download_all(
                        owner="yuanyan3060", repo="ArknightsGameResource", route=route, branch="main"
                    )
        except RequestException as e:
            logger.error(f"下载游戏资源失败: {e}")
            return
        if isinstance(version, str):
            GameResourceDownloader.update_version_file(version)
            logger.success(f"游戏资源已更新到版本：{version}")
