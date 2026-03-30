from nonebot import logger, get_driver
from nonebot_plugin_alconna import command_manager

from .config import CACHE_DIR, config
from .exception import RequestException
from .utils import download_img_resource
from .data_source import gacha_table_data, ef_gacha_pool_data

driver = get_driver()
shortcut_cache = CACHE_DIR / "shortcut.db"
from .matcher import skland, skland_command


@driver.on_startup
async def startup():
    try:
        await gacha_table_data.load()
    except RequestException as e:
        logger.error(f"检查卡池数据更新加载失败: {e}")
    logger.debug("Skland gacha table data loaded")
    try:
        await ef_gacha_pool_data.load()
    except RequestException as e:
        logger.error(f"终末地卡池数据加载失败: {e}")
    logger.debug("Endfield gacha pool table data loaded")
    command_manager.load_cache(shortcut_cache, command=skland_command)
    logger.debug("Skland shortcuts cache loaded")
    skland.shortcut("森空岛绑定", {"command": "skland bind", "fuzzy": True, "prefix": True})
    skland.shortcut("扫码绑定", {"command": "skland qrcode", "fuzzy": False, "prefix": True})
    skland.shortcut("森空岛解绑", {"command": "skland unbind", "fuzzy": False, "prefix": True})
    skland.shortcut("明日方舟签到", {"command": "skland arksign sign --all", "fuzzy": False, "prefix": True})
    skland.shortcut("签到详情", {"command": "skland arksign status", "fuzzy": False, "prefix": True})
    skland.shortcut("全体签到", {"command": "skland arksign all", "fuzzy": False, "prefix": True})
    skland.shortcut("全体签到详情", {"command": "skland arksign status --all", "fuzzy": False, "prefix": True})
    skland.shortcut("界园肉鸽", {"command": "skland rogue --topic 界园", "fuzzy": True, "prefix": True})
    skland.shortcut("萨卡兹肉鸽", {"command": "skland rogue --topic 萨卡兹", "fuzzy": True, "prefix": True})
    skland.shortcut("萨米肉鸽", {"command": "skland rogue --topic 萨米", "fuzzy": True, "prefix": True})
    skland.shortcut("水月肉鸽", {"command": "skland rogue --topic 水月", "fuzzy": True, "prefix": True})
    skland.shortcut("傀影肉鸽", {"command": "skland rogue --topic 傀影", "fuzzy": True, "prefix": True})
    skland.shortcut("角色更新", {"command": "skland char update", "fuzzy": False, "prefix": True})
    skland.shortcut("全体角色更新", {"command": "skland char update --all", "fuzzy": False, "prefix": True})
    skland.shortcut("资源更新", {"command": "skland sync", "fuzzy": True, "prefix": True})
    skland.shortcut("战绩详情", {"command": "skland rginfo", "fuzzy": True, "prefix": True})
    skland.shortcut("收藏战绩详情", {"command": "skland rginfo -f", "fuzzy": True, "prefix": True})
    skland.shortcut("方舟抽卡记录", {"command": "skland gacha -l 3", "fuzzy": True, "prefix": True})
    skland.shortcut("导入抽卡记录", {"command": "skland import", "fuzzy": True, "prefix": True})
    skland.shortcut("终末地签到", {"command": "skland efsign sign --all", "fuzzy": False, "prefix": True})
    skland.shortcut("终末地全体签到", {"command": "skland efsign all", "fuzzy": False, "prefix": True})
    skland.shortcut("终末地签到详情", {"command": "skland efsign status", "fuzzy": False, "prefix": True})
    skland.shortcut("终末地全体签到详情", {"command": "skland efsign status --all", "fuzzy": False, "prefix": True})
    skland.shortcut(r"(ef|zmd)", {"command": "skland efcard", "fuzzy": True, "prefix": True})
    skland.shortcut("终末地抽卡记录", {"command": "skland efgacha", "fuzzy": True, "prefix": True})
    skland.shortcut("终末地抽卡更新", {"command": "skland efgacha -u", "fuzzy": True, "prefix": True})

    if config.check_res_update:
        try:
            await download_img_resource(force=False, update=False)
        except RequestException as e:
            logger.error(f"资源下载失败: {e}")


@driver.on_shutdown
async def shutdown():
    command_manager.dump_cache(shortcut_cache, command=skland_command)
    logger.debug("Skland shortcuts cache dumped")
