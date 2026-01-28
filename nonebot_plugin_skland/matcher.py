"""命令定义和匹配器"""

from nonebot import require

require("nonebot_plugin_alconna")
from arclet.alconna import config as alc_config
from nonebot_plugin_argot import ArgotExtension
from nonebot_plugin_alconna.builtins.extensions import ReplyRecordExtension
from nonebot_plugin_alconna import (
    At,
    Args,
    Field,
    Option,
    Alconna,
    Namespace,
    Subcommand,
    CommandMeta,
    on_alconna,
)

ns = Namespace("skland", disable_builtin_options=set())
alc_config.namespaces["skland"] = ns

skland_command = Alconna(
    "skland",
    Args["target?#目标", At | int],
    Subcommand(
        "-b|--bind|bind",
        Args["token", str, Field(completion=lambda: "请输入 token 或 cred 完成绑定")],
        Option("-u|--update|update", help_text="更新绑定的 token 或 cred"),
        help_text="绑定森空岛账号",
    ),
    Subcommand("-q|--qrcode|qrcode", help_text="获取二维码进行扫码绑定"),
    Subcommand(
        "arksign",
        Subcommand(
            "sign",
            Option(
                "-u|--uid|uid",
                Args["uid", str, Field(completion=lambda: "请输入指定绑定角色uid")],
                help_text="指定个人绑定的角色uid进行签到",
            ),
            Option("--all", help_text="签到所有个人绑定的角色"),
            help_text="个人绑定角色签到",
        ),
        Subcommand(
            "status",
            Option("--all", help_text="查看所有绑定角色签到状态(仅超管可用)"),
            help_text="查看绑定角色签到状态",
        ),
        Subcommand("all", help_text="签到所有绑定角色(仅超管可用)"),
        help_text="明日方舟森空岛签到相关功能",
    ),
    Subcommand(
        "zmdsign",
        Subcommand(
            "sign",
            Option(
                "-u|--uid|uid",
                Args["uid", str, Field(completion=lambda: "请输入指定绑定角色uid")],
                help_text="指定个人绑定的角色uid进行签到",
            ),
            Option("--all", help_text="签到所有个人绑定的角色"),
            help_text="个人绑定角色签到",
        ),
        Subcommand(
            "status",
            Option("--all", help_text="查看所有绑定角色签到状态(仅超管可用)"),
            help_text="查看绑定角色签到状态",
        ),
        Subcommand("all", help_text="签到所有绑定角色(仅超管可用)"),
        help_text="终末地森空岛签到相关功能",
    ),
    Subcommand("char", Option("-u|--update|update"), help_text="更新绑定角色信息"),
    Subcommand(
        "sync",
        Option("-f|--force|force", help_text="强制更新"),
        Option("--img", help_text="更新图片资源(仅超管可用)"),
        Option("--data", help_text="更新数据资源(仅超管可用)"),
        Option("-u|--update|update", help_text="更新时下载并替换已有图片文件"),
        help_text="同步游戏资源",
    ),
    Subcommand(
        "rogue",
        Args["target?#目标", At | int],
        Option(
            "-t|--topic|topic",
            Args[
                "topic_name#主题",
                ["傀影", "水月", "萨米", "萨卡兹", "界园"],
                Field(completion=lambda: "请输入指定topic_id"),
            ],
            help_text="指定主题进行肉鸽战绩查询",
        ),
        help_text="肉鸽战绩查询",
    ),
    Subcommand(
        "rginfo",
        Args["id#战绩ID", int, Field(completion=lambda: "请输入战绩ID进行查询")],
        Option("-f|--favored|favored", help_text="是否查询收藏的战绩"),
        help_text="查询单局肉鸽战绩详情",
    ),
    Subcommand(
        "gacha",
        Args["target?#目标", At | int],
        Option("-b|--begin|begin", Args["begin", int], help_text="查询起始位置"),
        Option("-l|--limit|limit", Args["limit", int], help_text="查询抽卡记录卡池渲染上限"),
    ),
    Subcommand(
        "import", Args["url", str, Field(completion=lambda: "请输入抽卡记录导出链接")], help_text="导入抽卡记录"
    ),
    namespace=alc_config.namespaces["skland"],
    meta=CommandMeta(
        description="通过森空岛查询游戏数据",
        usage="skland --help",
        example="/skland",
    ),
)

skland = on_alconna(
    skland_command,
    aliases={"sk"},
    comp_config={"lite": True},
    skip_for_unmatch=False,
    use_cmd_start=True,
    extensions=[ArgotExtension, ReplyRecordExtension],
)

skland.shortcut("森空岛绑定", {"command": "skland bind", "fuzzy": True, "prefix": True})
skland.shortcut("扫码绑定", {"command": "skland qrcode", "fuzzy": False, "prefix": True})
skland.shortcut("明日方舟签到", {"command": "skland arksign sign --all", "fuzzy": False, "prefix": True})
skland.shortcut("签到详情", {"command": "skland arksign status", "fuzzy": False, "prefix": True})
skland.shortcut("全体签到", {"command": "skland arksign all", "fuzzy": False, "prefix": True})
skland.shortcut("全体签到详情", {"command": "skland arksign status --all", "fuzzy": False, "prefix": True})
skland.shortcut("界园肉鸽", {"command": "skland rogue --topic 界园", "fuzzy": True, "prefix": True})
skland.shortcut("萨卡兹肉鸽", {"command": "skland rogue --topic 萨卡兹", "fuzzy": True, "prefix": True})
skland.shortcut("萨米肉鸽", {"command": "skland rogue --topic 萨米", "fuzzy": True, "prefix": True})
skland.shortcut("水月肉鸽", {"command": "skland rogue --topic 水月", "fuzzy": True, "prefix": True})
skland.shortcut("傀影肉鸽", {"command": "skland rogue --topic 傀影", "fuzzy": True, "prefix": True})
skland.shortcut("角色更新", {"command": "skland char update", "fuzzy": False, "prefix": True})
skland.shortcut("资源更新", {"command": "skland sync", "fuzzy": True, "prefix": True})
skland.shortcut("战绩详情", {"command": "skland rginfo", "fuzzy": True, "prefix": True})
skland.shortcut("收藏战绩详情", {"command": "skland rginfo -f", "fuzzy": True, "prefix": True})
skland.shortcut("方舟抽卡记录", {"command": "skland gacha", "fuzzy": True, "prefix": True})
skland.shortcut("导入抽卡记录", {"command": "skland import", "fuzzy": True, "prefix": True})
skland.shortcut("终末地签到", {"command": "skland zmdsign sign --all", "fuzzy": False, "prefix": True})
skland.shortcut("终末地全体签到", {"command": "skland zmdsign all", "fuzzy": False, "prefix": True})
skland.shortcut("终末地签到详情", {"command": "skland zmdsign status", "fuzzy": False, "prefix": True})
skland.shortcut("终末地全体签到详情", {"command": "skland zmdsign status --all", "fuzzy": False, "prefix": True})
