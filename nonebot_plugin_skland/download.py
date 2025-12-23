import asyncio
from pathlib import Path
from itertools import islice
from datetime import datetime
from urllib.parse import quote
from collections.abc import Iterable

from nonebot import logger
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from pydantic import BaseModel
from nonebot.compat import model_validator
from httpx import Timeout, HTTPError, AsyncClient, TimeoutException
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

    def make_tasks_table(self, tasks: Iterable[Task]) -> Table:
        table = Table.grid(padding=(0, 1), expand=self.expand)
        tasks_table = Table.grid(padding=(0, 1), expand=self.expand)
        all_tasks_finished = True
        visible_tasks = list(islice((task for task in tasks if task.visible), self.MAX_VISIBLE_TASKS))

        for task in visible_tasks:
            status = self.STATUS_FIN if task.finished else self.STATUS_DL
            itable = Table.grid(padding=(0, 1), expand=self.expand)
            filename_column = Text(f"{task.fields['filename']}")
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

    DOWNLOAD_COUNT: int = 0
    DOWNLOAD_TIME: datetime
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
    async def check_update(cls, dir: Path) -> str | None:
        """检查更新"""
        origin_version = await cls.get_version()
        version_file = dir.joinpath("version")
        if not version_file.exists():
            return origin_version
        local_version = version_file.read_text(encoding="utf-8").strip()
        if origin_version != local_version:
            return origin_version
        return None

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
        cls.download_count = 0
        cls.download_time = datetime.now()
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
                            cls.download_count += 1
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

        time_consumed = datetime.now() - cls.download_time
        failed_count = len(failed_files)

        if cls.download_count == 0 and failed_count == 0:
            logger.info(f"✅ 资源 {route} 无新增文件")
        elif cls.download_count == 0 and failed_count > 0:
            logger.warning(f"⚠️ 资源 {route} 无新增文件，但有 {failed_count} 个文件下载失败")
        else:
            success_msg = f"🎉 资源 {route} 下载完成，成功 {cls.download_count} 个"
            if failed_count > 0:
                success_msg += f"，失败 {failed_count} 个"
            success_msg += f"，耗时 {time_consumed}"
            logger.success(success_msg)

        return DownloadResult(
            version=None,
            success_count=cls.download_count,
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
