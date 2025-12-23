import json
import random
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import httpx
from nonebot import logger
from pydantic import Field
from pydantic import BaseModel
from pydantic import AnyUrl as Url
from nonebot.compat import PYDANTIC_V2
import nonebot_plugin_localstore as store
from nonebot.plugin import get_plugin_config

from .exception import RequestException

if TYPE_CHECKING:
    from .schemas import CharTable, GachaTable, GachaDetails

RES_DIR: Path = Path(__file__).parent / "resources"
TEMPLATES_DIR: Path = RES_DIR / "templates"
CACHE_DIR = store.get_plugin_cache_dir()
DATA_DIR = store.get_plugin_data_dir()
RESOURCE_ROUTES = ["portrait", "skill", "avatar"]
DATA_ROUTES = ["gamedata/excel/gacha_table.json", "gamedata/excel/character_table.json"]
GACHA_DATA_PATH = DATA_DIR / "gamedata" / "excel"


class GachaTableData:
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


class CustomSource(BaseModel):
    uri: Url | Path

    def to_uri(self) -> Any:
        if isinstance(self.uri, Path):
            uri = self.uri
            if not uri.is_absolute():
                uri = Path(store.get_plugin_data_dir() / uri)

            if uri.is_dir():
                # random pick a file
                files = [f for f in uri.iterdir() if f.is_file()]
                logger.debug(f"CustomSource: {uri} is a directory, random pick a file: {files}")
                if PYDANTIC_V2:
                    return Url((uri / random.choice(files)).as_posix())
                else:
                    return Url((uri / random.choice(files)).as_posix(), scheme="file")  # type: ignore

            if not uri.exists():
                raise FileNotFoundError(f"CustomSource: {uri} not exists")
            if PYDANTIC_V2:
                return Url(uri.as_posix())
            else:
                return Url(uri.as_posix(), scheme="file")  # type: ignore

        return self.uri


class ScopedConfig(BaseModel):
    github_proxy_url: str = ""
    """GitHub 代理 URL"""
    github_token: str = ""
    """GitHub Token"""
    check_res_update: bool = False
    """启动时检查资源更新"""
    background_source: Literal["default", "Lolicon", "random"] | CustomSource = "default"
    """背景图片来源"""
    rogue_background_source: Literal["default", "rogue", "Lolicon"] | CustomSource = "rogue"
    """Rogue 战绩查询背景图片来源"""
    argot_expire: int = 300
    """Argot 缓存过期时间"""
    gacha_render_max: int = 30
    """抽卡记录单图渲染上限"""


class Config(BaseModel):
    skland: ScopedConfig = Field(default_factory=ScopedConfig)


config = get_plugin_config(Config).skland
gacha_table_data = GachaTableData()
