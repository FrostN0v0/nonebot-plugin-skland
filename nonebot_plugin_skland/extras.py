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
                "追加 `-r <序号>` 时只签到所选角色，不带参数时仍签到本人全部角色。\n\n"
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
                "查看本人全部角色的签到详情；可追加 `-r <序号>` 仅查看对应角色，不可与 `--all` 同用。"
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
                "追加 `-r <序号>` 时只签到所选角色，不带参数时仍签到本人全部角色。\n\n"
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
                "查看本人全部终末地角色的签到详情；可追加 `-r <序号>` 仅查看对应角色，不可与 `--all` 同用。"
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
            "func": "终末地战争回响",
            "trigger_method": "**已绑定用户**",
            "trigger_condition": "**终末地战争回响** | `skland efwar`",
            "brief_des": "查询终末地战争回响赛季、荣勋与轮换战绩。",
            "detail_des": (
                "- **终末地战争回响**\n\n"
                "```bash\n"
                "skland efwar [-r <index>] [-s <season>] [-w <week>]\n"
                "```\n\n"
                "默认展示当前赛季和当前轮换；`-s` / `-w` 使用卡片中的赛季、轮换序号，`-r` 临时选择自己的终末地角色。"
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
                "skland rogue --topic <topic> [-r <index>]\n"
                "```\n\n"
                " **快捷指令**：`<傀影|水月|萨米|萨卡兹|界园|树海>肉鸽`\n\n"
                "查询指定主题的肉鸽战绩。\n\n"
                "可追加 `-r <序号>` 临时选择自己的角色；不带选角参数时支持通过 @ 查询他人的默认角色。"
            ),
        },
        {
            "func": "战绩详情",
            "trigger_method": "**回复一条战绩图片消息或使用 -r 选角**",
            "trigger_condition": "**战绩详情** | `skland rginfo <id>`",
            "brief_des": "查询单局肉鸽战绩详情。",
            "detail_des": (
                "- **战绩详情**`\n"
                "```bash\n"
                "skland rginfo <id> [-r <index>]\n"
                "```\n\n"
                " **快捷指令** ：`战绩详情`\n\n"
                "查询指定战绩图中指定id的肉鸽战绩详情。\n\n"
                "> 不带 `-r` 时需回复战绩图；带 `-r` 时查询自己的指定角色，有回复时沿用该图主题，否则使用当前主题。\n"
                "- **收藏战绩详情**\n"
                "```bash\n"
                "skland rginfo <id> -f [-r <index>]\n"
                "```\n\n"
                " **快捷指令** ：`收藏战绩详情`\n\n"
                "查询指定战绩图中指定id的收藏战绩详情。\n\n"
                "> 收藏详情同样支持追加 `-r <序号>`。"
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
                "skland gacha [-r <index>] [-b <begin>] [-l <limit>]\n"
                "```\n\n"
                " **快捷指令** ：`方舟抽卡记录`\n\n"
                "查询默认角色的抽卡记录；可追加 `-r <序号>` 使用对应角色及其所属账号，不修改默认角色。"
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
                "选角使用 `-r` / `--role`，星级使用 `-ra` / `--rarity` 或自然筛选词；例 `方舟干员 -r 2 -ra 6`。\n\n"
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
            "brief_des": "获取、保存并展示终末地角色的最新抽卡记录。",
            "detail_des": (
                "- **终末地抽卡记录**\n\n"
                "```bash\n"
                "skland efgacha [-r <index>] [-b <begin>] [-l <limit>]\n"
                "```\n\n"
                " **快捷指令** ：`终末地抽卡记录`\n\n"
                "自动获取最新记录，去重保存后渲染；追加 `-r <序号>` 可临时选择自己的角色。\n"
                "`-b` / `-l` 只控制各类别卡池展示范围（限定/武器/联合/常驻/新手分别切片）。\n"
                "沿用终末地角色卡主题，三列固定为限定、武器、新手/常驻/联合；同类按时间倒序，原列续页，累计统计仅首页显示。\n\n"
                "> 接口不可用或未保存 token 时，有本地记录会明确标记为未更新的缓存；没有记录则提示原因。"
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
                "skland import <url> [-r <index>]\n"
                "```\n\n"
                " **快捷指令** ：`导入抽卡记录`\n\n"
                "可用 `-r <序号>` 指定导入角色；文件中的玩家 UID 必须与所选角色一致。\n"
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
            "trigger_condition": "**资源更新** | `skland sync --data`",
            "brief_des": "检查并更新游戏数据与卡池数据，不下载图片。",
            "detail_des": (
                "-  **资源更新**\n\n"
                "```bash\n"
                "skland sync --data\n"
                "```\n\n"
                "**快捷指令** ：资源更新\n\n"
                "快捷指令仅更新数据；手动 `skland sync` 仍同时更新图片与数据。\n"
                "每天 09:00 自动检查数据，沿用 APScheduler 时区（默认 Asia/Shanghai）；"
                "可设置 `skland__auto_update_resources=False` 关闭。\n\n"
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
                "> 数据按固定路径下载，不请求仓库文件树；下载或校验失败时保留旧数据。\n"
                "> 图片资源更新仍为可选操作，不在每日数据更新范围内。\n"
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
