"""Scheduled Skland sign and game-data update tasks."""

from nonebot import logger
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_orm import get_scoped_session

from .config import config
from .schemas import SignGame
from .exception import ResourceUpdateInProgress
from .services.resources import update_data_resources
from .services.sign import write_sign_cache, sign_all_characters


async def _run_daily_sign(game: SignGame) -> None:
    session = get_scoped_session()
    try:
        entries = await sign_all_characters(session, game)
        await session.commit()
        write_sign_cache(game, entries)
    finally:
        await session.close()


@scheduler.scheduled_job("cron", hour=0, minute=15, id="daily_arksign")
async def run_daily_arksign() -> None:
    """Run the daily Arknights sign task."""
    await _run_daily_sign("arknights")


@scheduler.scheduled_job("cron", hour=0, minute=20, id="daily_efsign")
async def run_daily_efsign() -> None:
    """Run the daily Endfield sign task."""
    await _run_daily_sign("endfield")


@scheduler.scheduled_job(
    "cron",
    hour=9,
    minute=0,
    id="daily_resource_update",
    max_instances=1,
    coalesce=True,
    misfire_grace_time=3600,
)
async def run_daily_resource_update() -> None:
    """Refresh game data without sending bot or group messages."""
    if not config.auto_update_resources:
        return
    try:
        result = await update_data_resources(refresh_metadata=True)
    except ResourceUpdateInProgress:
        logger.info("跳过每日数据资源更新：已有更新正在进行")
        return
    log = logger.warning if result.failed else logger.info
    log("每日数据资源更新：" + "；".join(result.messages))
