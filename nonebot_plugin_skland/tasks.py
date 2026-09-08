"""Scheduled Skland sign tasks."""

from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_orm import get_scoped_session

from .schemas import SignGame
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
