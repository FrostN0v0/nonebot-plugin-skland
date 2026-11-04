from arclet.alconna import Args, Alconna
from nonebot_plugin_alconna import on_alconna

command = Alconna("maa", Args["operation?", str]["argument?", str])
control = on_alconna(command, aliases={"MAA"}, use_cmd_start=True, priority=5, block=True)

for operation in ("管理", "绑定", "解绑", "状态", "截图", "停止", "结果", "证书"):
    for prefix in ("maa", "MAA"):
        control.shortcut(
            f"{prefix}{operation}",
            {"command": f"maa {operation}", "prefix": True, "fuzzy": False},
        )
