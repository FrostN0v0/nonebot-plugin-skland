import asyncio
from io import StringIO
from datetime import datetime, timedelta

import httpx
import pytest
from rich.console import Console


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


@pytest.mark.asyncio
async def test_data_client_bypasses_failed_proxy_without_exposing_github_token(app, monkeypatch):
    from nonebot_plugin_skland import download
    from nonebot_plugin_skland.config import config

    monkeypatch.setattr(config, "github_proxy_url", "https://gateway.example")
    monkeypatch.setattr(config, "github_token", "test-token")
    requests = []
    commit = "a" * 40

    def respond(request):
        requests.append(request)
        if request.url.host == "gateway.example":
            raise httpx.ConnectError("gateway unavailable", request=request)
        if request.url.host == "api.github.com":
            return httpx.Response(200, json={"object": {"sha": commit, "type": "commit"}})
        return httpx.Response(200, json={"version": "new"})

    monkeypatch.setattr(
        download, "AsyncClient", lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(respond), **kwargs)
    )
    async with download.GitHubDataClient() as client:
        assert await client.resolve_commit("owner", "repo", "main") == commit
        await client.get_json(f"https://raw.githubusercontent.com/owner/repo/{commit}/table.json")
        await client.get_json("https://prts.example/table.json")

    assert [request.url.host for request in requests] == [
        "gateway.example",
        "api.github.com",
        "raw.githubusercontent.com",
        "prts.example",
    ]
    assert requests[1].headers["Authorization"] == "Bearer test-token"
    assert all("Authorization" not in request.headers for request in (requests[0], requests[2], requests[3]))


@pytest.mark.asyncio
async def test_data_client_rejects_proxy_error_page_and_recovers_from_origin(app, monkeypatch):
    from nonebot_plugin_skland import download
    from nonebot_plugin_skland.config import config

    monkeypatch.setattr(config, "github_proxy_url", "https://gateway.example/")
    hosts = []

    def respond(request):
        hosts.append(request.url.host)
        if request.url.host == "gateway.example":
            return httpx.Response(200, text="<html>Temporarily unavailable</html>")
        return httpx.Response(200, json={"pool_name": "有效卡池"})

    monkeypatch.setattr(
        download, "AsyncClient", lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(respond), **kwargs)
    )
    async with download.GitHubDataClient() as client:
        data = await client.get_json("https://raw.githubusercontent.com/owner/repo/main/pools.json")
    assert data["pool_name"] == "有效卡池"
    assert hosts == ["gateway.example", "raw.githubusercontent.com"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "attempts"), [(503, 2), (404, 1)])
async def test_data_client_retries_transient_failures_only_and_redacts_urls(app, monkeypatch, mocker, status, attempts):
    from nonebot_plugin_skland import download
    from nonebot_plugin_skland.config import config
    from nonebot_plugin_skland.exception import RequestException

    monkeypatch.setattr(config, "github_proxy_url", "")
    seen = []

    def respond(request):
        seen.append(request)
        return httpx.Response(status, text="failure containing secret-value")

    monkeypatch.setattr(
        download, "AsyncClient", lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(respond), **kwargs)
    )
    mocker.patch.object(download.asyncio, "sleep", new=mocker.AsyncMock())
    async with download.GitHubDataClient() as client:
        with pytest.raises(RequestException) as error:
            await client.get_json("https://raw.githubusercontent.com/owner/repo/main/data.json?token=secret-value")
    assert len(seen) == attempts
    assert "secret-value" not in str(error.value)
    assert "raw.githubusercontent.com" not in str(error.value)


@pytest.mark.asyncio
async def test_data_client_bounds_concurrent_downloads(app, monkeypatch):
    from nonebot_plugin_skland import download
    from nonebot_plugin_skland.config import config

    monkeypatch.setattr(config, "github_proxy_url", "")
    release = asyncio.Event()
    at_capacity = asyncio.Event()
    active = 0
    peak = 0

    async def respond(request):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == 8:
            at_capacity.set()
        try:
            await release.wait()
            return httpx.Response(200, json={"name": request.url.path})
        finally:
            active -= 1

    monkeypatch.setattr(
        download, "AsyncClient", lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(respond), **kwargs)
    )
    async with download.GitHubDataClient() as client:
        pending = [asyncio.create_task(client.get_json(f"https://example.com/{i}.json")) for i in range(10)]
        try:
            await asyncio.wait_for(at_capacity.wait(), 5)
        finally:
            release.set()
            await asyncio.gather(*pending)
    assert peak == 8


@pytest.mark.asyncio
@pytest.mark.parametrize("ending", ["complete", "interrupted", "cancelled"])
async def test_data_download_shows_progress_before_completion_and_clears_after_exit(app, monkeypatch, ending):
    from nonebot_plugin_skland import download
    from nonebot_plugin_skland.config import config
    from nonebot_plugin_skland.exception import RequestException

    monkeypatch.setattr(config, "github_proxy_url", "")
    monkeypatch.setenv("TERM", "xterm-256color")
    screen = StringIO()
    console = Console(file=screen, force_terminal=True, color_system=None, width=100)
    progress = download.DownloadProgress(console=console, auto_refresh=False)
    monkeypatch.setattr(download, "DownloadProgress", lambda: progress)
    first_chunk = asyncio.Event()
    release = asyncio.Event()
    payload = b'{"name":"' + b"a" * 2037 + b'"}'

    class DelayedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield payload[:1024]
            first_chunk.set()
            await release.wait()
            if ending == "interrupted":
                raise httpx.ReadError("connection interrupted")
            yield payload[1024:]

    def respond(request):
        return httpx.Response(200, headers={"Content-Length": str(len(payload))}, stream=DelayedStream())

    monkeypatch.setattr(
        download, "AsyncClient", lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(respond), **kwargs)
    )
    async with download.GitHubDataClient() as client:
        running = asyncio.create_task(client.get_json("https://example.com/game-data.json"))
        try:
            await asyncio.wait_for(first_chunk.wait(), 5)
            assert not running.done()
            screen.seek(0)
            screen.truncate()
            progress.refresh()
            frame = screen.getvalue()
            assert "game-data.json" in frame
            assert "50%" in frame
            if ending == "cancelled":
                running.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await running
            else:
                release.set()
                if ending == "interrupted":
                    with pytest.raises(RequestException):
                        await running
                else:
                    await running
            with console.capture() as final_frame:
                progress.refresh()
            assert "game-data.json" not in final_frame.get()
        finally:
            release.set()
            if not running.done():
                running.cancel()
            await asyncio.gather(running, return_exceptions=True)


@pytest.fixture
def progress_logging(app, monkeypatch):
    from nonebot import logger
    import nonebot.log as nonebot_log

    monkeypatch.setenv("TERM", "xterm-256color")
    terminal = StringIO()
    file_log = StringIO()
    terminal_id = logger.add(
        terminal,
        format=nonebot_log.default_format,
        filter=nonebot_log.default_filter,
        level=0,
        colorize=False,
    )
    file_id = logger.add(file_log, format="{message}", colorize=False)
    monkeypatch.setattr(nonebot_log, "logger_id", terminal_id)
    try:
        yield terminal, file_log
    finally:
        try:
            logger.remove(nonebot_log.logger_id)
        except ValueError:
            pass
        logger.remove(file_id)


@pytest.mark.parametrize("interactive", [True, False])
def test_download_frame_coordinates_logs_and_leaves_no_frame_in_redirected_output(progress_logging, interactive):
    from nonebot import logger

    from nonebot_plugin_skland.download import DownloadProgress

    terminal, file_log = progress_logging
    console = Console(file=terminal, force_terminal=interactive, color_system=None, width=100)
    with DownloadProgress(console=console, auto_refresh=False) as progress:
        assert terminal.getvalue() == ""
        first = progress.add_task("Downloading", filename="first.json", total=100)
        second = progress.add_task("Downloading", filename="second-longer-name.json", total=100)
        progress.update(first, completed=25)
        progress.refresh()
        assert ("Downloading Files" in terminal.getvalue()) is interactive
        offset = terminal.tell()
        logger.info("download-log-marker")
        log_frame = terminal.getvalue()[offset:]
        if interactive:
            assert log_frame.index("\x1b[2K") < log_frame.index("download-log-marker")
            assert log_frame.index("download-log-marker") < log_frame.index("Downloading Files")
            assert log_frame.index("\n", log_frame.index("download-log-marker")) < log_frame.index("Downloading Files")
        else:
            assert "\x1b" not in log_frame
        progress.remove_task(first)
        logger.warning("remaining-log-marker")
        progress.remove_task(second)
        offset = terminal.tell()
        logger.success("completion-log-marker")
        completed = terminal.getvalue()[offset:]
        assert "completion-log-marker" in completed
        assert "Downloading Files" not in completed
        assert "\x1b" not in completed

    logger.info("after-download-marker")
    assert file_log.getvalue().splitlines() == [
        "download-log-marker",
        "remaining-log-marker",
        "completion-log-marker",
        "after-download-marker",
    ]
    if not interactive:
        assert "Downloading Files" not in terminal.getvalue()
        assert "\x1b" not in terminal.getvalue()


def test_progress_does_not_overwrite_a_user_console_sink_change(progress_logging):
    from nonebot import logger
    import nonebot.log as nonebot_log

    from nonebot_plugin_skland.download import DownloadProgress

    terminal, _ = progress_logging
    custom_log = StringIO()
    console = Console(file=terminal, force_terminal=True, color_system=None, width=100)
    with DownloadProgress(console=console, auto_refresh=False) as progress:
        task = progress.add_task("Downloading", filename="data.json", total=100)
        logger.remove(nonebot_log.logger_id)
        nonebot_log.logger_id = logger.add(custom_log, format="{message}", colorize=False)
        progress.remove_task(task)
    logger.info("custom-sink-still-active")
    assert custom_log.getvalue() == "custom-sink-still-active\n"


def test_overlapping_download_display_does_not_take_over_active_console(progress_logging):
    from nonebot import logger

    from nonebot_plugin_skland.download import DownloadProgress

    terminal, file_log = progress_logging
    console = Console(file=terminal, force_terminal=True, color_system=None, width=100)
    with DownloadProgress(console=console, auto_refresh=False) as first:
        active = first.add_task("Downloading", filename="active.json", total=100)
        with DownloadProgress(console=console, auto_refresh=False) as second:
            other = second.add_task("Downloading", filename="other.json", total=100)
            second.remove_task(other)
        offset = terminal.tell()
        logger.info("still-coordinated")
        output = terminal.getvalue()[offset:]
        assert output.index("\x1b[2K") < output.index("still-coordinated")
        assert "active.json" in output
        first.remove_task(active)
    logger.info("overlap-finished")
    assert file_log.getvalue().splitlines() == ["still-coordinated", "overlap-finished"]
