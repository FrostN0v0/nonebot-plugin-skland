from nonebot import logger, get_driver
from nonebot_plugin_alconna import command_manager

from .exception import RequestException
from .utils import download_img_resource
from .config import CACHE_DIR, config, gacha_table_data

driver = get_driver()
shortcut_cache = CACHE_DIR / "shortcut.db"


@driver.on_startup
async def startup():
    try:
        await gacha_table_data.load()
    except RequestException as e:
        logger.error(f"检查卡池数据更新加载失败: {e}")
    logger.debug("Skland gacha table data loaded")
    command_manager.load_cache(shortcut_cache)
    logger.debug("Skland shortcuts cache loaded")
    if config.check_res_update:
        try:
            await download_img_resource(force=False, update=False)
        except RequestException as e:
            logger.error(f"资源下载失败: {e}")


@driver.on_shutdown
async def shutdown():
    command_manager.dump_cache(shortcut_cache)
    logger.debug("Skland shortcuts cache dumped")
