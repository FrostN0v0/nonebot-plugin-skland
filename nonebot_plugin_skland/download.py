import re
import json
import asyncio
from pathlib import Path
from itertools import islice
from datetime import datetime
from typing import Any, TypeVar
from typing_extensions import Self
from urllib.parse import quote, urlsplit
from collections.abc import Callable, Iterable

from nonebot import logger
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from pydantic import BaseModel
import nonebot.log as nonebot_log
from rich.errors import LiveError
from nonebot.compat import model_validator
from httpx import Limits, Timeout, HTTPError, AsyncClient, HTTPStatusError, TimeoutException
from rich.progress import (
    Task,
    TaskID,
    Progress,
    BarColumn,
    TextColumn,
    DownloadColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from .exception import RequestException

DataT = TypeVar("DataT")


class GitHubDataClient:
    """One data update's connection pool, bounded retries, and proxy fallback."""

    def __init__(self) -> None:
        from .config import config

        prefix = config.github_proxy_url.strip()
        self._proxy = f"{prefix.rstrip('/')}/" if prefix else ""
        self._token = config.github_token.strip()
        self._proxy_failed = False
        concurrency = 8
        self._semaphore = asyncio.Semaphore(concurrency)
        self._progress = DownloadProgress()
        self._client = AsyncClient(
            timeout=Timeout(60.0, connect=10.0, pool=10.0),
            limits=Limits(max_connections=concurrency, max_keepalive_connections=concurrency),
            headers={"User-Agent": "nonebot-plugin-skland data updater", "Cache-Control": "no-cache"},
            follow_redirects=True,
        )

    async def __aenter__(self) -> Self:
        await self._client.__aenter__()
        try:
            self._progress.start()
        except BaseException:
            await self._client.aclose()
            raise
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        try:
            self._progress.stop()
        finally:
            await self._client.__aexit__(exc_type, exc_value, traceback)

    @staticmethod
    def _json_object(content: bytes) -> dict[str, Any]:
        value = json.loads(content)
        if not isinstance(value, dict) or not value:
            raise ValueError("Expected a nonempty JSON object")
        return value

    async def _fetch(self, url: str, parse: Callable[[bytes], DataT], *, filename: str | None = None) -> DataT:
        host = urlsplit(url).hostname
        use_proxy = bool(self._proxy) and host in {"api.github.com", "raw.githubusercontent.com", "github.com"}
        candidates = [(f"{self._proxy}{url}", True), (url, False)] if use_proxy else [(url, False)]
        failure = "请求失败"
        for candidate, proxied in candidates:
            if proxied and self._proxy_failed:
                continue
            headers = {}
            if not proxied and host == "api.github.com" and self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            for attempt in range(2):
                try:
                    async with self._semaphore:
                        if proxied and self._proxy_failed:
                            break
                        async with self._client.stream("GET", candidate, headers=headers) as response:
                            response.raise_for_status()
                            if filename is None:
                                content = await response.aread()
                            else:
                                length = response.headers.get("Content-Length", "")
                                total = int(length) if length.isdecimal() else None
                                task_id = self._progress.add_task("Downloading", filename=filename, total=total)
                                try:
                                    chunks = []
                                    async for chunk in response.aiter_bytes():
                                        chunks.append(chunk)
                                        self._progress.update(task_id, completed=response.num_bytes_downloaded)
                                    content = b"".join(chunks)
                                finally:
                                    self._progress.remove_task(task_id)
                            return parse(content)
                except HTTPStatusError as error:
                    status = error.response.status_code
                    failure = f"HTTP {status}"
                    transient = status in {408, 429} or status >= 500
                except HTTPError as error:
                    failure = type(error).__name__
                    transient = True
                except ValueError:
                    failure = "返回的数据格式无效"
                    transient = False
                if proxied:
                    # Do not repeat a dead gateway timeout for every file in this update.
                    if transient or failure == "返回的数据格式无效":
                        self._proxy_failed = True
                    break
                if not transient or attempt == 1:
                    break
                await asyncio.sleep(0.5)
        raise RequestException(f"数据下载失败：{failure}")

    async def resolve_commit(self, owner: str, repo: str, branch: str) -> str:
        def parse(content: bytes) -> str:
            data = self._json_object(content)
            reference = data.get("object")
            if not isinstance(reference, dict) or reference.get("type") != "commit":
                raise ValueError("Expected a commit reference")
            sha = reference.get("sha")
            if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
                raise ValueError("Invalid commit SHA")
            return sha

        url = (
            f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
            f"/git/ref/heads/{quote(branch, safe='')}"
        )
        return await self._fetch(url, parse)

    async def get_text(self, url: str) -> str:
        def parse(content: bytes) -> str:
            value = content.decode("utf-8-sig").strip()
            if not value or "<" in value or any(character.isspace() for character in value):
                raise ValueError("Expected a version identifier")
            return value

        return await self._fetch(url, parse)

    async def get_json(self, url: str) -> dict[str, Any]:
        filename = urlsplit(url).path.rsplit("/", 1)[-1]
        logger.info(f"正在下载: {filename}")
        started_at = datetime.now()
        result = await self._fetch(url, self._json_object, filename=filename)
        logger.success(f"🎉 资源 {filename} 下载完成，成功 1 个，耗时 {datetime.now() - started_at}")
        return result


class File(BaseModel):
    name: str
    download_url: str

    @model_validator(mode="before")
    @classmethod
    def modify_download_url(cls, values):
        from .config import config

        values["download_url"] = quote(values["download_url"], safe="/:")
        if config.github_proxy_url:
            values["download_url"] = f"{config.github_proxy_url}{values['download_url']}"
            return values
        return values


class DownloadResult(BaseModel):
    version: str | None
    success_count: int
    failed_count: int


class DownloadProgress(Progress):
    """下载进度条"""

    STATUS_DL = TextColumn("[blue]Downloading...")
    STATUS_FIN = TextColumn("[green]Complete!")
    STATUS_ROW = (
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%", justify="center"),
        TimeRemainingColumn(compact=True),
    )
    PROG_ROW = (DownloadColumn(binary_units=True), BarColumn(), TransferSpeedColumn())

    MAX_VISIBLE_TASKS = 10

    def __init__(self, *columns, **kwargs) -> None:
        kwargs["transient"] = True
        kwargs.setdefault("expand", True)
        super().__init__(*columns, **kwargs)
        self.disable = self.disable or not self.console.is_interactive
        self._log_handler: int | None = None
        self._log_stream = None

    def _add_console_sink(self, sink, *, colorize: bool | None = None) -> int:
        return logger.add(
            sink,
            level=0,
            diagnose=False,
            filter=nonebot_log.default_filter,
            format=nonebot_log.default_format,
            colorize=colorize,
        )

    def _write_log(self, message: str) -> None:
        self.console.print(Text.from_ansi(message), highlight=False, soft_wrap=True)

    def _restore_console_sink(self) -> None:
        if self._log_stream is None:
            return
        restore = self._log_handler is None or nonebot_log.logger_id == self._log_handler
        if self._log_handler is not None:
            try:
                logger.remove(self._log_handler)
            except ValueError:
                restore = False
        if restore:
            nonebot_log.logger_id = self._add_console_sink(self._log_stream)
        self._log_handler = None
        self._log_stream = None

    def start(self) -> None:
        if self.disable or self.live.is_started or not self.task_ids:
            return
        stream = self.console.file
        try:
            super().start()
        except LiveError:
            self.disable = True
            return
        # Only borrow NoneBot's default console sink; leave user/file sinks untouched.
        try:
            logger.remove(nonebot_log.logger_id)
        except ValueError:
            super().stop()
            self.disable = True
            return
        self._log_stream = stream
        try:
            self._log_handler = self._add_console_sink(
                self._write_log, colorize=self.console.is_terminal and not self.console.no_color
            )
            nonebot_log.logger_id = self._log_handler
        except BaseException:
            super().stop()
            self._restore_console_sink()
            raise

    def stop(self) -> None:
        if not self.live.is_started:
            return
        try:
            super().stop()
        finally:
            self._restore_console_sink()

    def add_task(
        self,
        description: str,
        start: bool = True,
        total: float | None = 100.0,
        completed: int = 0,
        visible: bool = True,
        **fields: Any,
    ) -> TaskID:
        task_id = super().add_task(description, start, total, completed, visible, **fields)
        self.start()
        return task_id

    def remove_task(self, task_id: TaskID) -> None:
        super().remove_task(task_id)
        if self.task_ids:
            self.refresh()
        else:
            self.stop()

    def make_tasks_table(self, tasks: Iterable[Task]) -> Table:
        table = Table.grid(padding=(0, 1), expand=self.expand)
        tasks_table = Table.grid(padding=(0, 1), expand=self.expand)
        all_tasks_finished = True
        visible_tasks = list(islice((task for task in tasks if task.visible), self.MAX_VISIBLE_TASKS))

        for task in visible_tasks:
            status = self.STATUS_FIN if task.finished else self.STATUS_DL
            itable = Table.grid(padding=(0, 1), expand=self.expand)
            filename_column = Text(str(task.fields["filename"]), no_wrap=True, overflow="ellipsis")
            itable.add_row(
                filename_column,
                *(column(task) for column in [status, *self.STATUS_ROW]),
            )
            itable.add_row(*(column(task) for column in self.PROG_ROW))
            tasks_table.add_row(itable)
            if not task.finished:
                all_tasks_finished = False

        if any(not task.finished for task in tasks):
            all_tasks_finished = False

        if all_tasks_finished:
            return table
        else:
            table.add_row(
                Panel(
                    tasks_table,
                    title="Downloading Files",
                    title_align="left",
                    padding=(1, 2),
                )
            )

        return table


class GameResourceDownloader:
    """游戏数据下载"""

    SEMAPHORE = asyncio.Semaphore(100)
    RAW_BASE_URL = "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/"
    VERSION_URL = "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/refs/heads/main/version"
    BASE_URL = "https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"

    @classmethod
    async def get_version(cls) -> str:
        """获取最新版本"""
        from .config import config

        url = config.github_proxy_url + cls.VERSION_URL if config.github_proxy_url else cls.VERSION_URL
        try:
            async with AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                origin_version = response.content.decode()
                return origin_version
        except HTTPError as e:
            raise RequestException(f"检查更新失败: {type(e).__name__}: {e}")

    @classmethod
    def update_version_file(cls, version: str):
        """更新本地版本文件"""
        from .config import CACHE_DIR

        version_file = CACHE_DIR.joinpath("version")
        version_file.write_text(version, encoding="utf-8")

    @classmethod
    async def fetch_file_list(cls, url: str, dl_url: str, route: str) -> list[File]:
        """获取 GitHub 仓库下的所有文件，并返回可下载的 URL"""
        from .config import config

        headers = {}
        if config.github_token:
            headers = {"Authorization": f"{config.github_token}"}
        try:
            async with AsyncClient() as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                is_file_path = "." in route.split("/")[-1]

                if is_file_path:

                    def path_filter(path):
                        return path == route
                else:
                    dir_route = route.rstrip("/") + "/"

                    def path_filter(path):
                        return path.startswith(dir_route)

                files = [
                    File(
                        name=item["path"].split("/")[-1],
                        download_url=f"{dl_url}{item['path']}",
                    )
                    for item in data.get("tree", [])
                    if item["type"] == "blob" and path_filter(item["path"])
                ]
                return files
        except HTTPError as e:
            raise RequestException(f"获取文件列表失败: {type(e).__name__}: {e}")

    @classmethod
    async def download_all(
        cls, owner: str, repo: str, route: str, save_dir: Path, branch: str = "main", update: bool = False
    ) -> DownloadResult:
        """并行下载 GitHub 目录下的所有文件

        Returns:
            DownloadResult: 下载结果，包含版本号、成功数量和失败数量
        """
        success_count = 0
        started_at = datetime.now()
        url = cls.BASE_URL.format(owner=owner, repo=repo, branch=branch)
        dl_url = cls.RAW_BASE_URL.format(owner=owner, repo=repo, branch=branch)
        files = await cls.fetch_file_list(url=url, dl_url=dl_url, route=route)
        is_file_path = "." in route.split("/")[-1]
        save_path = save_dir / route
        if is_file_path:
            save_path = save_path.parent
        save_path.mkdir(parents=True, exist_ok=True)

        failed_files = []
        timeout = Timeout(timeout=300.0, connect=30.0, read=60.0, write=30.0, pool=10.0)
        async with AsyncClient(timeout=timeout) as client:
            with DownloadProgress(
                "[cyan]{task.fields[filename]}",
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ) as progress:

                async def worker(file: File):
                    """每个文件下载任务"""
                    nonlocal success_count

                    if not update and (save_path / file.name).exists():
                        return
                    async with cls.SEMAPHORE:
                        task_id = progress.add_task("Downloading", filename=file.name, total=0)
                        try:
                            await cls.download_file(
                                client,
                                file,
                                save_path,
                                progress,
                                task_id=task_id,
                            )
                            success_count += 1
                        except TimeoutException as e:
                            error_msg = f"下载文件 {file.name} 超时: {e}"
                            failed_files.append(error_msg)
                        except RequestException as e:
                            error_msg = f"下载文件 {file.name} 失败: {e}"
                            failed_files.append(error_msg)
                        except Exception as e:
                            error_msg = f"下载文件 {file.name} 时发生未知错误: {type(e).__name__}: {e}"
                            failed_files.append(error_msg)
                        finally:
                            progress.remove_task(task_id)

                await asyncio.gather(*(worker(file) for file in files))

        if failed_files:
            logger.error(f"❌ 资源 {route} 有 {len(failed_files)} 个文件下载失败:")
            for error_msg in failed_files:
                logger.error(f"  - {error_msg}")

        time_consumed = datetime.now() - started_at
        failed_count = len(failed_files)

        if success_count == 0 and failed_count == 0:
            logger.info(f"✅ 资源 {route} 无新增文件")
        elif success_count == 0 and failed_count > 0:
            logger.warning(f"⚠️ 资源 {route} 无新增文件，但有 {failed_count} 个文件下载失败")
        else:
            success_msg = f"🎉 资源 {route} 下载完成，成功 {success_count} 个"
            if failed_count > 0:
                success_msg += f"，失败 {failed_count} 个"
            success_msg += f"，耗时 {time_consumed}"
            logger.success(success_msg)

        return DownloadResult(
            version=None,
            success_count=success_count,
            failed_count=failed_count,
        )

    @classmethod
    async def download_file(
        cls,
        client: AsyncClient,
        file: File,
        save_path: Path,
        progress: Progress,
        *,
        task_id: TaskID,
        **kwargs,
    ):
        """下载单个文件"""

        file_path = save_path / file.name
        try:
            async with client.stream("GET", file.download_url, **kwargs) as response:
                response.raise_for_status()
                file_size = int(response.headers.get("Content-Length", 0))
                progress.update(task_id, total=file_size)

                with file_path.open("wb") as f:
                    async for data in response.aiter_bytes(1024):
                        f.write(data)
                        progress.update(task_id, advance=len(data))
        except HTTPError as e:
            raise RequestException(f"下载文件{file.name}失败: {type(e).__name__}: {e}")


async def download_img_resource(force: bool, update: bool) -> DownloadResult:
    """Download image resources, optionally bypassing version checks or replacing files."""
    from .config import CACHE_DIR, RESOURCE_ROUTES

    origin_version = await GameResourceDownloader.get_version()
    version_file = CACHE_DIR.joinpath("version")
    local_version = version_file.read_text(encoding="utf-8") if version_file.exists() else None
    if local_version == origin_version and not force:
        logger.info("游戏图片资源已是最新版本")
        return DownloadResult(version=None, success_count=0, failed_count=0)

    logger.info(f"检测到新版本 {origin_version}，开始下载游戏资源")
    total_success = 0
    total_failed = 0
    for route in RESOURCE_ROUTES:
        logger.info(f"正在下载: {route}")
        result = await GameResourceDownloader.download_all(
            owner="yuanyan3060",
            repo="ArknightsGameResource",
            route=route,
            save_dir=CACHE_DIR,
            branch="main",
            update=update,
        )
        total_success += result.success_count
        total_failed += result.failed_count
    GameResourceDownloader.update_version_file(origin_version)
    logger.success(f"游戏资源已更新到版本：{origin_version}")
    return DownloadResult(
        version=origin_version,
        success_count=total_success,
        failed_count=total_failed,
    )
