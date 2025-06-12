import random
from pathlib import Path
from typing import Any, Literal

from nonebot import logger
from pydantic import Field
from pydantic import BaseModel
from pydantic import AnyUrl as Url
from nonebot.compat import PYDANTIC_V2
import nonebot_plugin_localstore as store
from nonebot.plugin import get_plugin_config

RES_DIR: Path = Path(__file__).parent / "resources"
TEMPLATES_DIR: Path = RES_DIR / "templates"
CACHE_DIR = store.get_plugin_cache_dir()
RESOURCE_ROUTES = ["portrait", "skill", "avatar"]


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


class Config(BaseModel):
    skland: ScopedConfig = Field(default_factory=ScopedConfig)


config = get_plugin_config(Config).skland
