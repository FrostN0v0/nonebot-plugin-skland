extra_data = {
    "menu_data": [
        {
            "func": "森空岛绑定",
            "trigger_method": "私聊",
            "trigger_condition": "**森空岛绑定** | `skland bind`",
            "brief_des": "森空岛绑定 <token|cred>",
            "detail_des": (
                "- **绑定账号**\n\n"
                "```bash\n"
                "skland bind <token|cred>\n"
                "```\n\n"
                " **快捷指令** ：`森空岛绑定`\n\n"
                "如需要更新绑定的森空岛账号，请使用 `skland bind -u <token|cred>` 更新绑定信息。\n"
                "其中 `token` 和 `cred` 的获取可以参考 `https://docs.qq.com/doc/p/2f705965caafb3ef342d4a979811ff3960bb3c17`。\n"
            ),
        },
        {
            "func": "扫码绑定",
            "trigger_method": "无限制",
            "trigger_condition": "**扫码绑定** | `skland qrcode`",
            "brief_des": "森空岛扫码绑定",
            "detail_des": (
                "- **扫码绑定**\n\n"
                "```bash\n"
                "skland qrcode\n"
                "```\n\n"
                " **快捷指令** ：`扫码绑定`\n\n"
                "如需要使用二维码绑定森空岛账号，请使用 `skland qrcode` 获取二维码。\n"
                "然后在两分钟内使用手机森空岛APP扫码登录以绑定森空岛账号。\n"
            ),
        },
        {
            "func": "skland",
            "trigger_method": "**已绑定用户**",
            "trigger_condition": "**skland**",
            "brief_des": "查询明日方舟角色信息卡片",
            "detail_des": (
                "- **查询明日方舟角色信息**\n\n"
                "```bash\n"
                "skland @某人 or 平台ID(QQ号)\n"
                "```\n\n"
                "**注意**: 如有多游戏角色绑定，默认查询森空岛设置的默认角色。"
            ),
        },
        {
            "func": "明日方舟签到",
            "trigger_method": "**已绑定用户**",
            "trigger_condition": "**明日方舟签到** | `skland arksign sign --all`",
            "brief_des": "签到绑定的明日方舟账号。",
            "detail_des": (
                "- **明日方舟签到**\n\n"
                "```bash\n"
                "skland arksign sign -all\n"
                "```\n\n"
                " **快捷指令** ：`明日方舟签到`\n\n"
                "签到绑定森空岛账号下的所有明日方舟角色。\n\n"
                "- **指定UID角色签到**\n\n"
                "```bash\n"
                "skland arksign sign -u <uid>\n"
                "```\n\n"
                "可以签到绑定的指定UID角色。\n\n"
                "> **注意：** 一般不需要进行手动签到，插件会在每天的00:15以后自动签到。"
            ),
        },
        {
            "func": "签到详情",
            "trigger_method": "**已绑定用户**",
            "trigger_condition": "**签到详情** | `skland arksign status`",
            "brief_des": "查看绑定角色的自动签到状态。",
            "detail_des": (
                "- **签到详情**\n\n"
                "```bash\n"
                "skland arksign status\n"
                "```\n\n"
                " **快捷指令** ：`签到详情`\n\n"
                "查看绑定角色的签到详情。"
            ),
        },
        {
            "func": "全体签到",
            "trigger_method": "**超级用户**",
            "trigger_condition": "**全体签到** | `skland arksign all`",
            "brief_des": "签到所有绑定到bot的明日方舟账号。",
            "detail_des": (
                "- **全体签到**\n\n"
                "```bash\n"
                "skland arksign all\n"
                "```\n\n"
                " **快捷指令** ：`全体签到`\n\n"
                "签到所有绑定到bot的明日方舟账号。\n\n"
            ),
        },
        {
            "func": "全体签到详情",
            "trigger_method": "**超级用户**",
            "trigger_condition": "**全体签到详情** | `skland arksign status --all`",
            "brief_des": "查看所有绑定角色的签到状态。",
            "detail_des": (
                "- **全体签到详情**\n\n"
                "```bash\n"
                "skland arksign status --all\n"
                "```\n\n"
                " **快捷指令** ：`全体签到详情`\n\n"
                "查看所有绑定角色的签到状态。\n\n"
            ),
        },
        {
            "func": "终末地签到",
            "trigger_method": "**已绑定用户**",
            "trigger_condition": "**终末地签到** | `skland efsign sign --all`",
            "brief_des": "签到绑定的终末地账号。",
            "detail_des": (
                "- **终末地签到**\n\n"
                "```bash\n"
                "skland efsign sign --all\n"
                "```\n\n"
                " **快捷指令** ：`终末地签到`\n\n"
                "签到绑定森空岛账号下的所有终末地角色。\n\n"
                "- **指定UID角色签到**\n\n"
                "```bash\n"
                "skland efsign sign -u <uid>\n"
                "```\n\n"
                "可以签到绑定的指定UID角色。\n\n"
                "> **注意：** 一般不需要进行手动签到，插件会在每天的00:20以后自动签到。"
            ),
        },
        {
            "func": "终末地签到详情",
            "trigger_method": "**已绑定用户**",
            "trigger_condition": "**终末地签到详情** | `skland efsign status`",
            "brief_des": "查看绑定角色的终末地自动签到状态。",
            "detail_des": (
                "- **终末地签到详情**\n\n"
                "```bash\n"
                "skland efsign status\n"
                "```\n\n"
                " **快捷指令** ：`终末地签到详情`\n\n"
                "查看绑定角色的终末地签到详情。"
            ),
        },
        {
            "func": "终末地全体签到",
            "trigger_method": "**超级用户**",
            "trigger_condition": "**终末地全体签到** | `skland efsign all`",
            "brief_des": "签到所有绑定到bot的终末地账号。",
            "detail_des": (
                "- **终末地全体签到**\n\n"
                "```bash\n"
                "skland efsign all\n"
                "```\n\n"
                " **快捷指令** ：`终末地全体签到`\n\n"
                "签到所有绑定到bot的终末地账号。\n\n"
            ),
        },
        {
            "func": "终末地全体签到详情",
            "trigger_method": "**超级用户**",
            "trigger_condition": "**终末地全体签到详情** | `skland efsign status --all`",
            "brief_des": "查看所有绑定角色的终末地签到状态。",
            "detail_des": (
                "- **终末地全体签到详情**\n\n"
                "```bash\n"
                "skland efsign status --all\n"
                "```\n\n"
                " **快捷指令** ：`终末地全体签到详情`\n\n"
                "查看所有绑定角色的终末地签到状态。\n\n"
            ),
        },
        {
            "func": "终末地角色卡片",
            "trigger_method": "**已绑定用户**",
            "trigger_condition": "**ef** | `skland efcard`",
            "brief_des": "查询终末地角色信息卡片。",
            "detail_des": (
                "- **终末地角色卡片**\n\n"
                "```bash\n"
                "skland efcard [@某人 | QQ号]\n"
                "```\n\n"
                " **快捷指令** ：`ef`\n\n"
                "查询终末地角色信息卡片。\n\n"
                "**可选参数：**\n"
                "- `-a` / `--all`：展示所有角色（默认按森空岛配置过滤）\n"
                "- `-s` / `--simple`：使用简化背景\n"
            ),
        },
        {
            "func": "<傀影|水月|萨米|萨卡兹|界园>肉鸽",
            "trigger_method": "**无限制**",
            "trigger_condition": "**<傀影|水月|萨米|萨卡兹|界园>肉鸽** | `skland rogue --topic <主题>`",
            "brief_des": "查询指定主题的肉鸽战绩。",
            "detail_des": (
                "- **<傀影|水月|萨米|萨卡兹|界园>肉鸽**\n\n"
                "```bash\n"
                "skland rogue --topic <主题>\n"
                "```\n\n"
                " **快捷指令**：`<傀影|水月|萨米|萨卡兹|界园>肉鸽`\n\n"
                "查询指定主题的肉鸽战绩。\n\n"
                "支持添加`@`参数查询指定用户的肉鸽战绩。"
            ),
        },
        {
            "func": "战绩详情",
            "trigger_method": "**回复一条战绩图片消息**",
            "trigger_condition": "**战绩详情** | `skland rginfo <id>`",
            "brief_des": "查询单局肉鸽战绩详情。",
            "detail_des": (
                "- **战绩详情**`\n"
                "```bash\n"
                "skland rginfo <id>\n"
                "```\n\n"
                " **快捷指令** ：`战绩详情`\n\n"
                "查询指定战绩图中指定id的肉鸽战绩详情。\n\n"
                "> 需要回复一条通过肉鸽战绩查询指令获取到的战绩图消息。\n"
                "- **收藏战绩详情**\n"
                "```bash\n"
                "skland rginfo <id> -f\n"
                "```\n\n"
                " **快捷指令** ：`收藏战绩详情`\n\n"
                "查询指定战绩图中指定id的收藏战绩详情。\n\n"
                "> 需要回复一条通过肉鸽战绩查询指令获取到的战绩图消息。"
            ),
        },
        {
            "func": "方舟抽卡记录",
            "trigger_method": "**无限制**",
            "trigger_condition": "**方舟抽卡记录** | `skland gacha`",
            "brief_des": "查询绑定到bot的明日方舟账号的抽卡记录。",
            "detail_des": (
                "- **方舟抽卡记录**\n\n"
                "```bash\n"
                "skland gacha -b <起始id> -l <结束id>\n"
                "```\n\n"
                " **快捷指令** ：`方舟抽卡记录`\n\n"
                "查询绑定到bot的明日方舟账号的抽卡记录。"
            ),
        },
        {
            "func": "终末地抽卡记录",
            "trigger_method": "**无限制**",
            "trigger_condition": "**终末地抽卡记录** | `skland efgacha`",
            "brief_des": "查询绑定到bot的终末地账号的抽卡记录。",
            "detail_des": (
                "- **终末地抽卡记录**\n\n"
                "```bash\n"
                "skland efgacha -b <起始卡池序号> -l <结束卡池序号>\n"
                "```\n\n"
                " **快捷指令** ：`终末地抽卡记录`\n\n"
                "查询绑定到bot的终末地账号的抽卡记录。\n"
                "默认从数据库缓存读取渲染，添加 `-u` 参数从接口拉取最新数据并更新。\n"
                "支持 `-b` 和 `-l` 参数控制渲染的卡池范围，"
                "卡池数量超过上限时将自动分页发送多张图片。"
            ),
        },
        {
            "func": "导入抽卡记录",
            "trigger_method": "**已绑定用户**",
            "trigger_condition": "**导入抽卡记录** | `skland import`",
            "brief_des": "导入小黑盒明日方舟抽卡记录。",
            "detail_des": (
                "- **导入抽卡记录**\n\n"
                "```bash\n"
                "skland import <url>\n"
                "```\n\n"
                " **快捷指令** ：`导入抽卡记录`\n\n"
                "支持导入小黑盒记录的抽卡记录\n"
                "请滑动至小黑盒抽卡分析页底部，点击`数据管理`导出数据并复制链接"
            ),
        },
        {
            "func": "角色更新",
            "trigger_method": "**已绑定用户**",
            "trigger_condition": "**角色更新** | `skland char update`",
            "brief_des": "同步森空岛绑定的游戏角色信息。",
            "detail_des": (
                "-  **角色更新**\n\n"
                "```bash\n"
                "skland char update\n"
                "```\n\n"
                "**快捷指令** ：`角色更新`\n\n"
                "同步森空岛绑定的游戏角色信息。"
            ),
        },
        {
            "func": "全体角色更新",
            "trigger_method": "**超级用户**",
            "trigger_condition": "**全体角色更新** | `skland char update --all`",
            "brief_des": "更新所有绑定用户的角色信息。",
            "detail_des": (
                "-  **全体角色更新**\n\n"
                "```bash\n"
                "skland char update --all\n"
                "```\n\n"
                "**快捷指令** ：`全体角色更新`\n\n"
                "更新所有绑定到bot的用户角色信息。\n\n"
                "> **注意：** 该指令仅超管可用。"
            ),
        },
        {
            "func": "资源更新",
            "trigger_method": "**超级用户**",
            "trigger_condition": "**资源更新** | `skland sync`",
            "brief_des": "更新游戏资源（图片和数据）。",
            "detail_des": (
                "-  **资源更新**\n\n"
                "```bash\n"
                "skland sync\n"
                "```\n\n"
                "**快捷指令** ：资源更新\n\n"
                "同时更新游戏图片资源和数据资源。\n\n"
                "- **仅更新图片资源**\n\n"
                "```bash\n"
                "skland sync --img\n"
                "```\n\n"
                "仅更新游戏图片资源（干员立绘、技能图标等）。\n\n"
                "- **仅更新数据资源**\n\n"
                "```bash\n"
                "skland sync --data\n"
                "```\n\n"
                "仅更新游戏数据资源（卡池数据、角色数据等）。\n\n"
                "- **强制更新**\n\n"
                "```bash\n"
                "skland sync --force\n"
                "```\n\n"
                "强制重新下载资源，忽略版本检查。\n\n"
                "- **覆盖已有文件**\n\n"
                "```bash\n"
                "skland sync --update\n"
                "```\n\n"
                "更新图片资源时，覆盖已存在的图片文件。\n\n"
                "> 资源渲染优先读取本地资源，本地资源不存在时才从网络下载\n"
                "> 如果服务器网络资源不紧缺则无需下载一坨资源\n"
                "> 可以组合使用选项，例如 `skland sync --img --force --update`"
            ),
        },
        {
            "func": "暗语",
            "trigger_method": "**回复一条该插件渲染的图片消息**",
            "trigger_condition": "**background** | **clue**",
            "brief_des": "获取暗语消息。",
            "detail_des": (
                "- 目前暗语列表：\n\n"
                "|   暗语指令   |      对象      |    说明    |\n"
                "| :----------: | :------------: | :--------: |\n"
                "| `background` | `插件渲染卡片` | 查看背景图 |\n"
                "|    `clue`    | `游戏信息卡片` | 查看线索板 |\n"
            ),
        },
        {
            "func": "自定义指令",
            "trigger_method": "**超级用户**",
            "trigger_condition": "`/skland --shortcut`",
            "brief_des": "添加自定义指令，使用方法请看详情。",
            "detail_des": (
                "#### 🪄 自定义快捷指令\n\n"
                "> 该特性依赖于 `Alconna 快捷指令`"
                "自定义指令不带 `COMMAND_START`，若有必要需手动填写\n"
                "```bash\n"
                "# 增加\n"
                "/skland --shortcut <自定义指令> /skland\n"
                "# 删除\n"
                "/skland --shortcut delete <自定义指令>\n"
                "# 列出\n"
                "/skland --shortcut list\n"
                "```\n\n"
                "> 自定义指令中包含空格，需要用引号`"
                "`包裹。\n\n"
                "例子:\n\n"
                "```bash\n"
                'user: /skland --shortcut /兔兔签到 "/skland arksign sign --all"\n'
                'bot: skland::skland 的快捷指令: "/兔兔签到" 添加成功\n'
                "```\n"
            ),
        },
    ],
    "pmn": {"markdown": True},
}
