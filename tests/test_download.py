import asyncio
from datetime import datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_overlapping_downloads_keep_independent_counts_and_elapsed_time(app, tmp_path, mocker):
    from nonebot_plugin_skland import download

    downloader = download.GameResourceDownloader
    entered = {route: asyncio.Event() for route in ("first", "second")}
    release = {route: asyncio.Event() for route in entered}
    now = datetime(2026, 1, 1)
    messages = []

    async def fetch_files(*, url, dl_url, route):
        return [download.File(name=f"{route}.png", download_url=f"https://example.com/{route}.png")]

    async def download_file(client, file, save_path, progress, *, task_id):
        route = save_path.name
        entered[route].set()
        await release[route].wait()

    mocker.patch.object(downloader, "fetch_file_list", new=fetch_files)
    mocker.patch.object(downloader, "download_file", new=download_file)
    mocker.patch.object(download, "AsyncClient")
    # Disable only terminal rendering: concurrent Rich live displays are a separate constraint.
    mocker.patch.object(download, "DownloadProgress")
    mocker.patch.object(download, "datetime").now.side_effect = lambda: now
    mocker.patch.object(download.logger, "success", new=messages.append)

    tasks = []
    try:
        first = asyncio.create_task(downloader.download_all("owner", "repo", "first", tmp_path))
        tasks.append(first)
        await asyncio.wait_for(entered["first"].wait(), timeout=5)

        now += timedelta(seconds=10)
        second = asyncio.create_task(downloader.download_all("owner", "repo", "second", tmp_path))
        tasks.append(second)
        await asyncio.wait_for(entered["second"].wait(), timeout=5)

        now += timedelta(seconds=10)
        release["first"].set()
        first_result = await asyncio.wait_for(first, timeout=5)

        now += timedelta(seconds=20)
        release["second"].set()
        second_result = await asyncio.wait_for(second, timeout=5)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    assert (first_result.success_count, second_result.success_count) == (1, 1)
    assert (first_result.failed_count, second_result.failed_count) == (0, 0)
    assert str(timedelta(seconds=20)) in messages[0]
    assert str(timedelta(seconds=30)) in messages[1]


@pytest.mark.asyncio
async def test_resource_download_aggregates_skips_failures_and_version_updates(app, tmp_path, mocker):
    from nonebot_plugin_skland import download
    from nonebot_plugin_skland.exception import RequestException

    downloader = download.GameResourceDownloader
    version = "resource-release\n"
    mocker.patch("nonebot_plugin_skland.config.CACHE_DIR", tmp_path)
    mocker.patch("nonebot_plugin_skland.config.RESOURCE_ROUTES", ["portrait", "avatar"])
    mocker.patch.object(downloader, "get_version", return_value=version)
    mocker.patch.object(download, "AsyncClient")
    mocker.patch.object(download, "DownloadProgress")
    existing_file = tmp_path / "portrait" / "existing.png"
    existing_file.parent.mkdir()
    existing_file.write_bytes(b"existing")

    async def fetch_files(*, url, dl_url, route):
        names = ("existing.png", "new.png", "failed.png") if route == "portrait" else ("avatar.png",)
        return [download.File(name=name, download_url=f"https://example.com/{name}") for name in names]

    async def download_file(client, file, save_path, progress, *, task_id):
        if file.name == "failed.png":
            raise RequestException("Download failed")
        (save_path / file.name).write_bytes(b"updated")

    mocker.patch.object(downloader, "fetch_file_list", new=fetch_files)
    mocker.patch.object(downloader, "download_file", new=download_file)

    result = await download.download_img_resource(force=False, update=False)

    assert (result.version, result.success_count, result.failed_count) == (version, 2, 1)
    assert existing_file.read_bytes() == b"existing"
    assert (tmp_path / "portrait" / "new.png").read_bytes() == b"updated"
    assert (tmp_path / "avatar" / "avatar.png").read_bytes() == b"updated"
    assert not (tmp_path / "portrait" / "failed.png").exists()
    assert (tmp_path / "version").read_text(encoding="utf-8") == version

    current = await download.download_img_resource(force=False, update=True)

    assert (current.version, current.success_count, current.failed_count) == (None, 0, 0)
    assert existing_file.read_bytes() == b"existing"

    forced = await download.download_img_resource(force=True, update=False)

    assert (forced.version, forced.success_count, forced.failed_count) == (version, 0, 1)
    assert existing_file.read_bytes() == b"existing"

    replaced = await download.download_img_resource(force=True, update=True)

    assert (replaced.version, replaced.success_count, replaced.failed_count) == (version, 3, 1)
    assert existing_file.read_bytes() == b"updated"
    assert (tmp_path / "version").read_text(encoding="utf-8") == version
