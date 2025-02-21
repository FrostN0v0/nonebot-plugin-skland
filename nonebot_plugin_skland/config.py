from pydantic import BaseModel
from nonebot.plugin import get_plugin_config


class Config(BaseModel):
    your_plugin_config_here: str = "Hello World!"
    """ 你的插件配置项 """


config = get_plugin_config(Config)
