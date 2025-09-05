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
from httpx import HTTPError, AsyncClient
from nonebot.compat import model_validator
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
    def modify_download_url(cls, values):
        from .config import config

        values["download_url"] = quote(values["download_url"], safe="/:")
        if config.github_proxy_url:
            values["download_url"] = f"{config.github_proxy_url}{values['download_url']}"
            return values
        return values


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
    async def check_update(cls, dir: Path) -> str:
        """检查更新"""
        origin_version = await cls.get_version()
        version_file = dir.joinpath("version")
        if not version_file.exists():
            return origin_version
        local_version = version_file.read_text(encoding="utf-8").strip()
        if origin_version != local_version:
            return origin_version
        return ""

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
    ):
        """并行下载 GitHub 目录下的所有文件"""
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

        async with AsyncClient() as client:
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
                        await cls.download_file(
                            client,
                            file,
                            save_path,
                            progress,
                            task_id=task_id,
                            timeout=300,
                        )
                        progress.remove_task(task_id)
                        cls.download_count += 1

                await asyncio.gather(*(worker(file) for file in files))
        time_consumed = datetime.now() - cls.download_time
        if cls.download_count == 0:
            logger.info(f"✅ 资源 {route} 无新增文件")
        else:
            logger.success(f"🎉 资源 {route} 下载完成，共下载 {cls.download_count} 个文件,耗时 {time_consumed}")

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
                file_size = int(response.headers.get("Content-Length", 0))
                progress.update(task_id, total=file_size)

                with file_path.open("wb") as f:
                    async for data in response.aiter_bytes(1024):
                        f.write(data)
                        progress.update(task_id, advance=len(data))
        except HTTPError as e:
            raise RequestException(f"下载文件{file.name}失败: {type(e).__name__}: {e}")
