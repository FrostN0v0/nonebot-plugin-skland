from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Alconna, UniMessage, CommandMeta, on_alconna

from .config import config

__plugin_meta__ = PluginMetadata(
    name="插件发布名称",
    description="插件描述",
    usage="描述你的插件用法",
    type="application",
    homepage="https://github.com/owner/nonebot-plugin-example",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra={
        "author": "owner <your@email>",
        "version": "0.1.0",
    },
)

your_matcher = on_alconna(
    Alconna(
        "your_matcher",
        meta=CommandMeta(
            description=__plugin_meta__.description,
            usage=__plugin_meta__.usage,
            example="/your_matcher",
        ),
    ),
    block=True,
    use_cmd_start=True,
)


@your_matcher.handle()
async def _():
    await UniMessage(config.your_plugin_config_here).finish()
