"""Shared startup, manual, and scheduled game-data updates."""

import asyncio
from dataclasses import dataclass

from nonebot import logger

from ..download import GitHubDataClient
from ..data_source import gacha_table_data, ef_gacha_pool_data
from ..exception import RequestException, ResourceUpdateInProgress


@dataclass(frozen=True)
class ResourceUpdateResult:
    messages: tuple[str, ...]
    failed: bool


_update_lock = asyncio.Lock()


async def update_data_resources(*, force: bool = False, refresh_metadata: bool = True) -> ResourceUpdateResult:
    """Update both games independently, rejecting overlapping update requests."""
    if _update_lock.locked():
        raise ResourceUpdateInProgress("数据资源正在更新，请稍后再试")
    # Acquiring an unlocked asyncio lock does not suspend before taking ownership.
    async with _update_lock:
        messages: list[str] = []
        failed = False
        async with GitHubDataClient() as client:
            try:
                changed = await gacha_table_data.load(force=force, refresh_metadata=refresh_metadata, client=client)
                if changed:
                    version = gacha_table_data.version or "未知"
                    message = f"明日方舟数据资源更新成功，版本: {version}"
                else:
                    message = "明日方舟数据资源已是最新"
                logger.info(f"✅ {message}")
                messages.append(f"{'✅' if changed else '📦'} {message}")
            except RequestException as error:
                logger.error(f"明日方舟数据资源更新失败: {error}")
                messages.append(f"❌ 明日方舟数据资源更新失败: {error}")
                failed = True

            try:
                changed = await ef_gacha_pool_data.load(force=force, client=client)
                if changed:
                    message = f"终末地卡池数据更新成功，共 {len(ef_gacha_pool_data.pool_table)} 个卡池"
                else:
                    message = f"终末地卡池数据已是最新，共 {len(ef_gacha_pool_data.pool_table)} 个卡池"
                logger.info(f"✅ {message}")
                messages.append(f"{'✅' if changed else '📦'} {message}")
            except RequestException as error:
                logger.error(f"终末地卡池数据更新失败: {error}")
                messages.append(f"❌ 终末地卡池数据更新失败: {error}")
                failed = True

        return ResourceUpdateResult(messages=tuple(messages), failed=failed)
