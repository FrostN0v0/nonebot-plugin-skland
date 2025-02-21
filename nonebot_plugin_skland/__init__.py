from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

from .config import config

require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Alconna, UniMessage, CommandMeta, on_alconna

from .api import SklandAPI, SklandLoginAPI

__plugin_meta__ = PluginMetadata(
    name="明日方舟数据查询",
    description="通过森空岛查询游戏数据",
    usage="描述你的插件用法",
    type="application",
    homepage="https://github.com/FrostN0v0/nonebot-plugin-skland",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra={
        "author": "FrostN0v0 <1614591760@qq.com>",
        "version": "0.1.0",
    },
)

skland = on_alconna(
    Alconna(
        "skland",
        meta=CommandMeta(
            description=__plugin_meta__.description,
            usage=__plugin_meta__.usage,
            example="/skland",
        ),
    ),
    block=True,
    use_cmd_start=True,
)


@skland.handle()
async def _():
    await UniMessage(config.your_plugin_config_here).send()
