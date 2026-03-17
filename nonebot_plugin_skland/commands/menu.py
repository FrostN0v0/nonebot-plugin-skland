"""帮助菜单相关命令"""

import random

from nonebot_plugin_alconna import UniMessage

from ..extras import extra_data
from ..render import render_help_menu
from ..utils import get_background_image


async def menu_handler():
    """查询帮助菜单"""

    background = await get_background_image(random.choice(["ark", "endfield"]))
    image = await render_help_menu(extra_data, background)

    msg = UniMessage.image(raw=image)
    await msg.send(reply_to=True)
