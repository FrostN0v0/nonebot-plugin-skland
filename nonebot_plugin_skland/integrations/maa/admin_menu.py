"""Private superuser command directory; deliberately absent from public help."""

from nonebot import on_command
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot.adapters.qq import Bot, C2CMessageCreateEvent

ADMIN_COMMANDS = [
    ("/MAA证书", "查看远控 HTTPS 证书状态"),
    ("/skland sync [--img] [--data] [--force] [--update]", "更新资源"),
    ("/skland char update --all", "更新全体角色"),
    ("/skland arksign all", "全体方舟签到"),
    ("/skland arksign status --all", "全体方舟签到详情"),
    ("/skland efsign all", "全体终末地签到"),
    ("/skland efsign status --all", "全体终末地签到详情"),
]


async def private_qq(event):
    return isinstance(event, C2CMessageCreateEvent)


admin_menu = on_command("超管菜单", rule=private_qq, permission=SUPERUSER, priority=3, block=True)


@admin_menu.handle()
async def show_admin_menu(bot: Bot, event: C2CMessageCreateEvent, matcher: Matcher):
    # Explicit guard also covers direct invocation and future matcher changes.
    if not isinstance(event, C2CMessageCreateEvent) or not await SUPERUSER(bot, event):
        return
    await matcher.send("超管菜单（仅私聊）\n" + "\n".join(f"{cmd} — {text}" for cmd, text in ADMIN_COMMANDS))
