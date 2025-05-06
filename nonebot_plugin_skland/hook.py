from nonebot import logger, get_driver
from nonebot_plugin_alconna import command_manager

from .exception import RequestException
from .download import GameResourceDownloader
from .config import CACHE_DIR, RESOURCE_ROUTES, config

driver = get_driver()
shortcut_cache = CACHE_DIR / "shortcut.db"


@driver.on_startup
async def startup():
    command_manager.load_cache(shortcut_cache)
    logger.debug("Skland shortcuts cache loaded")
    if config.check_res_update:
        try:
            if version := await GameResourceDownloader.check_update():
                logger.info("开始下载游戏资源")
                for route in RESOURCE_ROUTES:
                    logger.info(f"正在下载: {route}")
                    await GameResourceDownloader.download_all(
                        owner="yuanyan3060",
                        repo="ArknightsGameResource",
                        route=route,
                        branch="main",
                    )
        except RequestException as e:
            logger.error(f"下载游戏资源失败: {e}")
            return
        if version:
            GameResourceDownloader.update_version_file(version)
            logger.success(f"游戏资源已更新到版本：{version}")


@driver.on_shutdown
async def shutdown():
    command_manager.dump_cache(shortcut_cache)
    logger.debug("Skland shortcuts cache dumped")
