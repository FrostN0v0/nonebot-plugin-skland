from pydantic import Field, BaseModel
from nonebot.plugin import get_plugin_config


class ScopedConfig(BaseModel):
    github_proxy_url: str = ""
    """GitHub 代理 URL"""
    github_token: str = ""
    """GitHub Token"""


class Config(BaseModel):
    skland: ScopedConfig = Field(default_factory=ScopedConfig)


config = get_plugin_config(Config).skland
