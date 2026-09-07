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
                "skland bind -u <token|cred>\n"
                "```\n\n"
                " **快捷指令** ：`森空岛绑定`\n\n"
                "同一用户可以绑定多个森空岛账号。插件会先展示该账号的角色列表，仅在命令发起者回复「确认」后保存。\n"
                "`-u` 只更新由凭证识别出的既有账号；不带 `-u` 时新增账号。\n"
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
                "在约两分钟内使用森空岛 App 扫码。扫码完成后插件会展示角色列表，"
                "只有命令发起者确认后才会保存或更新对应账号。\n"
            ),
        },
        {
            "func": "森空岛解绑",
            "trigger_method": "无限制",
            "trigger_condition": "**森空岛解绑** | `skland unbind`",
            "brief_des": "解绑森空岛账号",
            "detail_des": (
                "- **解绑账号**\n\n"
                "```bash\n"
                "skland unbind\n"
                "```\n\n"
                " **快捷指令** ：`森空岛解绑`\n\n"
                "先按卡片序号选择一个账号或回复「全部」，再进行第二次确认。只删除所选账号及其角色、抽卡记录；删除默认角色后需要重新选择。\n"
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
                "skland\n"
                "skland -r <index>\n"
                "skland <target>\n"
                "```\n\n"
                "默认查询插件中选择的明日方舟角色；`-r` / `--role` 按最新 `sk char` 的方舟角色序号临时查询自己的角色，"
                "不会修改默认角色。始终使用选中角色所属森空岛账号的凭证访问接口。"
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
                "skland arksign sign --all\n"
                "```\n\n"
                " **快捷指令** ：`明日方舟签到`\n\n"
                "签到绑定森空岛账号下的所有明日方舟角色。\n\n"
                "- **按角色序号签到**\n\n"
                "```bash\n"
                "skland arksign sign -r <index>\n"
                "```\n\n"
                "`-r` / `--role` 按方舟角色序号签到，不改默认；不可与 `--all` 同用。\n\n"
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
                "- **按角色序号签到**\n\n"
                "```bash\n"
                "skland efsign sign -r <index>\n"
                "```\n\n"
                "`-r` / `--role` 按终末地角色序号签到，不改默认；不可与 `--all` 同用。\n\n"
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
                "skland efcard -r <index>\n"
                "```\n\n"
                " **快捷指令** ：`ef`\n\n"
                "查询终末地角色信息卡片。\n\n"
                "**可选参数：**\n"
                "- `-r <序号>` / `--role <序号>`：按终末地角色序号临时查询自己，不改默认\n"
                "- `-a` / `--all`：展示所有角色（默认按森空岛配置过滤）\n"
                "- `-s` / `--simple`：使用简化背景\n"
            ),
        },
        {
            "func": "<傀影|水月|萨米|萨卡兹|界园|树海>肉鸽",
            "trigger_method": "**无限制**",
            "trigger_condition": "**<傀影|水月|萨米|萨卡兹|界园|树海>肉鸽** | `skland rogue --topic <主题>`",
            "brief_des": "查询指定主题的肉鸽战绩。",
            "detail_des": (
                "- **<傀影|水月|萨米|萨卡兹|界园|树海>肉鸽**\n\n"
                "```bash\n"
                "skland rogue --topic <主题>\n"
                "```\n\n"
                " **快捷指令**：`<傀影|水月|萨米|萨卡兹|界园|树海>肉鸽`\n\n"
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
            "func": "方舟干员",
            "trigger_method": "**已绑定用户**",
            "trigger_condition": "**方舟干员** | `skland box`",
            "brief_des": "使用中文筛选词查询持有干员、未拥有干员或完整图鉴。",
            "detail_des": (
                "- **方舟干员**\n\n"
                "直接在快捷指令后追加筛选词，例如：`方舟干员 6星 近卫 满潜`、"
                "`方舟干员 未拥有 5-6星`、`方舟干员 @某人 远程 女 最近`。\n\n"
                "**可直接使用的筛选词：**\n\n"
                "- 持有状态：`持有` / `已拥有`；`未拥有` / `未持有` / `缺失` / `缺干员`；"
                "`全部` / `图鉴`\n"
                "- 星级：`6星` / `6★` / `5-6星`\n"
                "- 职业：`先锋` / `近卫` / `重装` / `狙击` / `术师` / `医疗` / `辅助` / `特种`；"
                "职业分支可直接写 `铁卫` / `收割者` / `医师` 等中文名\n"
                "- 部署位置：`近战` / `近战位`；`远程` / `远程位`\n"
                "- 性别：`男` / `男性`；`女` / `女性` / `女士`；`其他` / `未知`\n"
                "- 势力与种族：直接写 `罗德岛` / `炎` / `萨卡兹` 等目录中文名\n"
                "- 潜能：`满潜`（潜能 6）/ `潜6` / `潜能6` / `6潜` / `潜3-6` / `潜能3-6` / `3-6潜`\n"
                "- 排序：`实装` / `实装顺序`；`获取` / `最近` / `最近获得` / `获取顺序`；"
                "`练度` / `练度排序`\n"
                "- 名称：直接输入干员名称或代号片段，或使用 `名字:阿米娅` / `名称:阿米娅`\n\n"
                "同一维度内为“或”，不同维度之间为“且”；筛选词之间必须使用空格。"
                "查询他人时将 @ 或 QQ 号放在筛选词之前。\n\n"
                "高级语法：`skland box [target] [filters ...] [options]`。"
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
                "skland efgacha [-b <起始卡池序号>] [-l <结束卡池序号>]\n"
                "```\n\n"
                " **快捷指令** ：`终末地抽卡记录`\n\n"
                "从数据库缓存读取并渲染终末地抽卡记录。\n"
                "支持 `-b` 和 `-l` 参数控制各类别渲染的卡池范围（限定/武器/常驻/新手分别计数），"
                "卡池数量超过上限时将自动分页发送多张图片。\n\n"
                "> **注意：** 首次使用或需要更新数据时，请使用 `终末地抽卡更新` 快捷指令。"
            ),
        },
        {
            "func": "终末地抽卡更新",
            "trigger_method": "**无限制**",
            "trigger_condition": "**终末地抽卡更新** | `skland efgacha -u`",
            "brief_des": "从接口拉取最新终末地抽卡记录并更新数据库。",
            "detail_des": (
                "- **终末地抽卡更新**\n\n"
                "```bash\n"
                "skland efgacha -u [-b <起始卡池序号>] [-l <结束卡池序号>]\n"
                "```\n\n"
                " **快捷指令** ：`终末地抽卡更新`\n\n"
                "从森空岛接口拉取最新终末地抽卡记录，去重后保存至数据库，再渲染输出。\n"
                "同样支持 `-b` 和 `-l` 参数控制渲染的卡池范围。\n\n"
                "> **注意：** 该操作需要请求接口，耗时较长。"
                "如无新增记录需要更新请使用 `终末地抽卡记录` 快捷指令。"
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
            "func": "账号角色管理",
            "trigger_method": "**已绑定用户**",
            "trigger_condition": "**森空岛角色** | **切换方舟角色** | **切换终末地角色** | `sk char` | **角色更新**",
            "brief_des": "查看全部账号角色、切换默认角色并同步角色。",
            "detail_des": (
                "- **账号角色管理**\n\n"
                "```bash\n"
                "skland char\n"
                "skland char set ark <index>\n"
                "skland char set ef <index>\n"
                "skland char update\n"
                "```\n\n"
                " **快捷指令** ：`森空岛角色`、`切换方舟角色 <序号>`、`切换终末地角色 <序号>`。\n\n"
                "`skland char` 返回全部森空岛账号及其角色卡片；明日方舟和终末地分别维护一个插件默认角色。\n"
                "角色序号按游戏独立生成，以最新卡片为准。`角色更新` 快捷指令对应 `skland char update`。"
                "\n临时查询使用 `sk -r <序号>` 或 `sk efcard -r <序号>`，无需先切换默认角色。"
            ),
        },
        {
            "func": "全体角色更新",
            "trigger_method": "**超级用户**",
            "trigger_condition": "**全体角色更新** | `skland char update --all`",
            "brief_des": "逐账号更新所有绑定角色。",
            "detail_des": (
                "-  **全体角色更新**\n\n"
                "```bash\n"
                "skland char update --all\n"
                "```\n\n"
                "**快捷指令** ：`全体角色更新`\n\n"
                "逐个森空岛账号同步角色；单个账号失败不会回滚其他已成功账号。\n\n"
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
