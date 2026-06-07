"""游戏数据加载与管理"""

import json
from typing import TYPE_CHECKING

import httpx
from nonebot import logger

from .exception import RequestException
from .config import DATA_DIR, DATA_ROUTES, GACHA_DATA_PATH, config

if TYPE_CHECKING:
    from .schemas import CharTable, GachaTable, GachaDetails
    from .schemas.endfield.gacha.base import EfGachaContentPool


class GachaTableData:
    """明日方舟卡池数据管理"""

    def __init__(self) -> None:
        self.version_file = DATA_DIR / "version"
        self.version: str | None = None
        if self.version_file.exists():
            try:
                self.version = self.version_file.read_text(encoding="utf-8").strip()
            except Exception as e:
                logger.warning(f"读取版本文件失败: {e}")
        self.origin_version: str | None = None
        self.gacha_table: list[GachaTable] = []
        self.gacha_details: list[GachaDetails] = []
        self.character_table: list[CharTable] = []

    async def get_gacha_details(self):
        from .schemas import GachaDetails

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get("https://weedy.prts.wiki/gacha_table.json")
                response.raise_for_status()
                data = response.json()["gachaPoolClient"]
                self.gacha_details = [GachaDetails(**item) for item in data]
        except httpx.HTTPError as e:
            raise RequestException(f"获取卡池详情失败: {type(e).__name__}: {e}")

    async def get_version(self):
        from .download import GameResourceDownloader

        self.origin_version = await GameResourceDownloader.check_update(DATA_DIR)

    async def download_game_data(self):
        from .download import GameResourceDownloader

        for route in DATA_ROUTES:
            logger.info(f"正在下载: {route}")
            await GameResourceDownloader.download_all(
                owner="yuanyan3060",
                repo="ArknightsGameResource",
                route=route,
                save_dir=DATA_DIR,
                branch="main",
                update=True,
            )

    def _update_version_file(self) -> None:
        """更新本地版本文件"""
        if self.origin_version:
            self.version_file.write_text(self.origin_version, encoding="utf-8")
            self.version = self.origin_version

    async def load(self, force: bool = False) -> bool:
        """加载卡池数据，返回是否进行了下载"""
        from .schemas import CharTable, GachaTable

        await self.get_version()
        if not self.version_file.exists() and self.origin_version:
            self._update_version_file()

        downloaded = False

        if force:
            logger.info("正在重新下载卡池数据...")
            await self.download_game_data()
            self._update_version_file()
            downloaded = True
        elif (
            GACHA_DATA_PATH.joinpath("gacha_table.json").exists()
            and GACHA_DATA_PATH.joinpath("character_table.json").exists()
        ):
            if self.version != self.origin_version and self.origin_version:
                logger.info("检测到卡池数据版本更新，正在重新下载卡池数据...")
                await self.download_game_data()
                self._update_version_file()
                downloaded = True
        else:
            await self.download_game_data()
            self._update_version_file()
            downloaded = True

        self.character_table = []
        self.gacha_table = []
        self.gacha_details = []

        try:
            char_json = json.loads(GACHA_DATA_PATH.joinpath("character_table.json").read_text(encoding="utf-8"))
            for char_id, data in char_json.items():
                char_table = CharTable(**data)
                char_table.char_id = char_id
                self.character_table.append(char_table)

            gacha_json = json.loads(GACHA_DATA_PATH.joinpath("gacha_table.json").read_text(encoding="utf-8"))
            self.gacha_table = [GachaTable(**item) for item in gacha_json.get("gachaPoolClient", [])]

            await self.get_gacha_details()
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            logger.error(f"加载卡池数据失败: {type(e).__name__}: {e}")
            raise RequestException(f"加载卡池数据失败，请尝试删除数据目录后重新启动: {e}")

        return downloaded


class EfGachaPoolTableData:
    """终末地卡池数据管理

    从 GitHub 仓库 FrostN0v0/EndfieldGachaPoolTable 拉取 GachaPoolTable.json，
    解析为 dict[str, EfGachaContentPool]，提供按 pool_id 查询卡池 UP 信息的能力。
    不做版本校验，每次启动或执行 sync 命令时直接覆盖下载。
    """

    RAW_URL = "https://raw.githubusercontent.com/FrostN0v0/EndfieldGachaPoolTable/master/GachaPoolTable.json"

    def __init__(self) -> None:
        self._file_path = DATA_DIR / "endfield" / "GachaPoolTable.json"
        self.pool_table: dict[str, EfGachaContentPool] = {}

    async def download(self) -> None:
        """从 GitHub 下载 GachaPoolTable.json（支持代理）"""
        url = f"{config.github_proxy_url}{self.RAW_URL}" if config.github_proxy_url else self.RAW_URL
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()
                self._file_path.parent.mkdir(parents=True, exist_ok=True)
                self._file_path.write_bytes(response.content)
                logger.info("✅ 终末地卡池数据下载完成")
        except httpx.HTTPError as e:
            raise RequestException(f"下载终末地卡池数据失败: {type(e).__name__}: {e}")

    async def load(self) -> None:
        """下载并加载终末地卡池数据

        下载失败时，若本地存在旧文件则使用旧缓存并发出警告，否则抛出异常。
        """
        try:
            await self.download()
        except RequestException as e:
            if self._file_path.exists():
                logger.warning(f"终末地卡池数据下载失败，使用本地缓存: {e}")
            else:
                raise

        self._parse()

    def _parse(self) -> None:
        """解析本地 GachaPoolTable.json"""
        from .schemas.endfield.gacha.base import EfGachaContentPool

        try:
            raw: dict = json.loads(self._file_path.read_text(encoding="utf-8"))
            self.pool_table = {pool_id: EfGachaContentPool(**data) for pool_id, data in raw.items()}
            logger.info(f"✅ 终末地卡池数据加载完成，共 {len(self.pool_table)} 个卡池")
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            logger.error(f"加载终末地卡池数据失败: {type(e).__name__}: {e}")
            raise RequestException(f"加载终末地卡池数据失败: {e}")

    def get_pool(self, pool_id: str) -> "EfGachaContentPool | None":
        """按 pool_id 查询卡池信息"""
        return self.pool_table.get(pool_id)


gacha_table_data = GachaTableData()
ef_gacha_pool_data = EfGachaPoolTableData()
