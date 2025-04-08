import random
from pathlib import Path
from typing import Literal

from nonebot import logger
from pydantic import Field
from pydantic import BaseModel
from pydantic import AnyUrl as Url
import nonebot_plugin_localstore as store
from nonebot.plugin import get_plugin_config

RES_DIR: Path = Path(__file__).parent / "resources"
TEMPLATES_DIR: Path = RES_DIR / "templates"
CACHE_DIR = store.get_plugin_cache_dir()


class CustomSource(BaseModel):
    uri: Url | Path

    def to_uri(self) -> Url:
        if isinstance(self.uri, Path):
            uri = self.uri
            if not uri.is_absolute():
                uri = Path(store.get_plugin_data_dir() / uri)

            if uri.is_dir():
                # random pick a file
                files = [f for f in uri.iterdir() if f.is_file()]
                logger.debug(f"CustomSource: {uri} is a directory, random pick a file: {files}")
                return Url((uri / random.choice(files)).as_posix())

            if not uri.exists():
                raise FileNotFoundError(f"CustomSource: {uri} not exists")

            return Url(uri.as_posix())

        return self.uri


class ScopedConfig(BaseModel):
    github_proxy_url: str = ""
    """GitHub 代理 URL"""
    github_token: str = ""
    """GitHub Token"""
    check_res_update: bool = True
    """检查资源更新"""
    background_source: Literal["default", "Lolicon", "random"] | CustomSource = "default"
    """背景图片来源"""


class Config(BaseModel):
    skland: ScopedConfig = Field(default_factory=ScopedConfig)


config = get_plugin_config(Config).skland
