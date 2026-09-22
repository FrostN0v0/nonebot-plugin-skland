from nonebot import get_driver

from .schemas.help import HelpEntry, HelpCategory

HELP_PREFIX = min(get_driver().config.command_start, key=lambda value: (len(value), value), default="")

HELP_ENTRIES = (
    HelpEntry(
        func="扫码绑定",
        category="account",
        command="扫码绑定",
        brief_des="用森空岛 App 扫码，确认角色后完成绑定",
        condition="群聊 / 私聊 · 推荐",
        examples=("扫码绑定", "sk qrcode"),
        detail_des=(
            "### 三步完成绑定\n\n"
            "1. 使用森空岛 App 扫描机器人发送的二维码\n"
            "2. 核对返回的账号角色卡片\n"
            "3. 由命令发起者回复 **确认**，保存或更新这个账号\n\n"
            "> 二维码约 100 秒后撤回  \n> 插件无法验证扫码者身份，请只确认自己的账号  \n> "
            "未确认、取消或超时均不会保存绑定"
        ),
    ),
    HelpEntry(
        func="森空岛绑定",
        category="account",
        command="森空岛绑定 <token|cred>",
        brief_des="通过凭证新增账号，或更新已有账号",
        condition="仅私聊 · 确认后保存",
        examples=("森空岛绑定 <token|cred>", "sk bind <token|cred> -u"),
        detail_des=(
            "### 新增与更新\n\n"
            "同一用户可以绑定多个森空岛账号  \n插件先展示账号的完整角色列表，"
            "只有命令发起者回复 **确认** 后才保存\n\n"
            "- 不带 `-u`：新增一个森空岛账号\n"
            "- 带 `-u`：更新凭证识别出的既有账号，不通过角色序号指定账号\n\n"
            "### 凭证安全\n\n"
            "不要在群聊发送 token、cred 或包含凭证的截图  \n"
            "也可以使用无需手动复制凭证的扫码绑定\n\n"
            "[token / cred 获取说明](https://docs.qq.com/doc/p/2f705965caafb3ef342d4a979811ff3960bb3c17)"
        ),
    ),
    HelpEntry(
        func="账号角色管理",
        category="account",
        command="森空岛角色",
        brief_des="查看角色序号，分别选择两游戏的默认角色",
        condition="已绑定用户",
        examples=("森空岛角色", "切换方舟角色 2", "切换终末地角色 1", "角色更新"),
        detail_des=(
            "### 角色与账号\n\n"
            "角色卡展示本人全部账号和角色  \n明日方舟、终末地各自维护一个插件默认角色，"
            "角色编号也按游戏独立生成，以最新卡片为准\n\n"
            "| 操作 | 标准子命令 |\n| --- | --- |\n"
            "| 查看全部角色 | `sk char` |\n"
            "| 切换方舟默认角色 | `sk char set ark <序号>` |\n"
            "| 切换终末地默认角色 | `sk char set ef <序号>` |\n"
            "| 同步账号角色 | `sk char update` |\n\n"
            "### 只想查一次其他角色？\n\n"
            "在支持选角的查询后追加 `-r <序号>` 即可，不需要先修改默认角色  \n"
            "临时选角只能选择自己的角色，不能与查询他人混用"
        ),
    ),
    HelpEntry(
        func="森空岛解绑",
        category="account",
        command="森空岛解绑",
        brief_des="按账号选择解绑，保留其他账号的记录",
        condition="已绑定用户 · 二次确认",
        examples=("森空岛解绑", "sk unbind"),
        detail_des=(
            "### 选择后再确认\n\n"
            "1. 按角色卡上的 **账号序号** 选择一个账号，或回复 **全部**\n"
            "2. 核对将要删除的账号，回复 **确认**\n\n"
            "> 会删除所选账号及其角色、抽卡记录  \n> 删除当前默认角色后不会自动切换到其他账号，"
            "需要重新选择默认角色  \n> 取消或超时不执行删除"
        ),
    ),
    HelpEntry(
        func="方舟角色卡片",
        category="arknights",
        command="sk",
        brief_des="理智、基建、招募与角色状态一图查看",
        condition="角色已绑定 · 支持查询他人",
        examples=("sk", "sk -r 2", "sk @某人"),
        detail_des=(
            "### 查询目标\n\n"
            "- 不带参数：查看本人默认明日方舟角色\n"
            "- `-r <序号>` / `--role <序号>`：临时查看自己的其他方舟角色，不修改默认\n"
            "- `@某人` 或 QQ 号：查看对方绑定的默认角色，不支持替对方临时选角\n\n"
            "### 图片还可以做什么\n\n"
            "回复卡片发送 `background` 获取背景；回复支持线索的角色卡发送 `clue` 查看线索板"
        ),
    ),
    HelpEntry(
        func="明日方舟签到",
        category="arknights",
        command="明日方舟签到",
        brief_des="签到本人全部方舟角色，也可按序号选择",
        condition="已绑定用户",
        examples=("明日方舟签到", "明日方舟签到 -r 2", "sk arksign sign --all"),
        detail_des=(
            "### 签到范围\n\n"
            "裸快捷指令签到本人全部方舟角色  \n追加 `-r <序号>` 时仅签到所选角色\n\n"
            "标准命令 `arksign sign --all` 的 `--all` 指 **本人的全部角色**，不是机器人全部用户  \n"
            "`-r` 与 `--all` 不可同时使用\n\n"
            "> 每天 00:15 自动执行方舟签到，通常无需手动操作  \n> 结果可通过「签到详情」查看"
        ),
    ),
    HelpEntry(
        func="签到详情",
        category="arknights",
        command="签到详情",
        brief_des="查看方舟签到结果和失败原因",
        condition="已绑定用户",
        examples=("签到详情", "签到详情 -r 2", "sk arksign status"),
        detail_des=(
            "### 查看范围\n\n"
            "默认展示本人全部方舟角色的缓存签到结果  \n追加 `-r <序号>` 仅查看该角色，"
            "不修改默认角色\n\n"
            "> 这里的 `status --all` 是超管查看机器人全部用户的入口，与个人选角互斥"
        ),
    ),
    HelpEntry(
        func="方舟干员",
        category="arknights",
        command="方舟干员 [筛选词]",
        brief_des="按星级、职业、潜能或练度筛选干员",
        condition="角色已绑定 · 筛选词用空格分隔",
        examples=("方舟干员 6星 近卫 满潜", "方舟干员 未拥有 5-6星", "方舟干员 -r 2 练度"),
        template="skland_roster",
        detail_des=(
            "### 自然筛选速查\n\n"
            "- **持有状态**：`持有` / `已拥有`、`未拥有` / `缺干员`、`全部` / `图鉴`\n"
            "- **星级**：`6星`、`5-6星`；裸数字不作为星级\n"
            "- **职业**：先锋、近卫、重装、狙击、术师、医疗、辅助、特种\n"
            "- **职业分支**：直接输入中文名，如 `铁卫`、`收割者`、`医师`\n"
            "- **部署位置**：`近战` / `近战位`、`远程` / `远程位`\n"
            "- **性别**：`男` / `男性`、`女` / `女性`、`其他` / `未知`\n"
            "- **势力 / 种族**：直接输入目录中文名，如 `罗德岛`、`炎`、`萨卡兹`\n"
            "- **潜能**：`满潜`、`潜6`、`潜能6`、`潜3-6`，范围为 1–6\n"
            "- **排序**：`实装`、`获取` / `最近`、`练度`\n"
            "- **名称**：名称或代号片段，也可输入 `名字:阿米娅`\n\n"
            "### 组合规则\n\n"
            "同一维度取 **或**，不同维度取 **且**；不要把多个筛选词连写  \n"
            "查询他人时，将 @ 或 QQ 号放在筛选词之前  \n未拥有模式不支持潜能、获取或练度条件\n\n"
            "### 高级选项\n\n"
            "| 维度 | 选项 |\n| --- | --- |\n"
            "| 角色 / 星级 | `-r` / `--role`；`-ra` / `--rarity` |\n"
            "| 持有 / 职业 / 分支 | `-o`；`-p`；`-b` |\n"
            "| 位置 / 性别 | `--position`；`--gender` |\n"
            "| 势力 / 种族 | `-f`；`--race` |\n"
            "| 潜能 / 排序 / 名称 | `--potential`；`-s`；`-n` |\n\n"
            "> 选角是 `-r`，星级是 `-ra`  \n> 自然筛选与高级选项可组合使用"
        ),
    ),
    HelpEntry(
        func="肉鸽战绩",
        category="arknights",
        command="水月肉鸽",
        brief_des="查看各集成战略主题的生涯与历史战绩",
        condition="角色已绑定 · 支持查询他人",
        examples=("水月肉鸽", "树海肉鸽 -r 2", "sk rogue @某人 --topic 萨米"),
        detail_des=(
            "### 六个主题\n\n"
            "快捷指令支持 **傀影肉鸽、水月肉鸽、萨米肉鸽、萨卡兹肉鸽、界园肉鸽、树海肉鸽**\n\n"
            "标准命令使用 `--topic <主题>`；树海对应的主题参数是 `黑流树海`  \n"
            "追加 `-r <序号>` 可临时选择自己的方舟角色\n\n"
            "### 继续查看单局\n\n"
            "回复战绩图片，发送「战绩详情 <ID>」查看指定一局；收藏记录使用「收藏战绩详情 <ID>」"
        ),
    ),
    HelpEntry(
        func="战绩详情",
        category="arknights",
        command="战绩详情 <ID>",
        brief_des="查看肉鸽单局详情与收藏记录",
        condition="回复战绩图片，或显式选角",
        examples=("战绩详情 1", "收藏战绩详情 1", "sk rginfo 1 -r 2"),
        detail_des=(
            "### 图片与角色\n\n"
            "- 不带 `-r`：需要回复战绩图片，读取这张图片携带的缓存记录\n"
            "- 带 `-r <序号>`：获取所选角色的新数据；有引用图片时沿用其主题，否则使用角色当前主题\n"
            "- `-f` / `--favored`：查询收藏记录，对应「收藏战绩详情」快捷指令\n\n"
            "ID 使用战绩图片中显示的记录编号"
        ),
    ),
    HelpEntry(
        func="方舟抽卡记录",
        category="arknights",
        command="方舟抽卡记录",
        brief_des="查看方舟寻访统计与卡池出货记录",
        condition="角色已绑定 · 支持查询他人",
        examples=("方舟抽卡记录", "方舟抽卡记录 -r 2", "sk gacha -b 1 -l 3"),
        detail_des=(
            "### 展示范围\n\n"
            "`-b <起点>` / `--begin` 与 `-l <数量>` / `--limit` 按 **卡池序号** 控制展示，"
            "不是抽数或日期  \n中文快捷指令默认展示 3 个卡池\n\n"
            "`-r <序号>` 使用自己的指定方舟角色及其账号，不修改默认角色；不带选角时可通过 @ 查询他人\n\n"
            "历史记录也可以通过「导入抽卡记录」从小黑盒补充"
        ),
    ),
    HelpEntry(
        func="导入抽卡记录",
        category="arknights",
        command="导入抽卡记录 <链接>",
        brief_des="将小黑盒导出的寻访记录导入对应角色",
        condition="已绑定用户 · 玩家 UID 须一致",
        examples=("导入抽卡记录 <链接>", "sk import <链接> -r 2"),
        detail_des=(
            "### 导出与导入\n\n"
            "滑动至小黑盒抽卡分析页底部，打开 **数据管理**，导出数据并复制链接  \n"
            "将链接作为命令参数发送给机器人\n\n"
            "默认导入本人默认方舟角色；追加 `-r <序号>` 指定其他角色  \n"
            "文件中的玩家 UID 必须与所选角色一致"
        ),
    ),
    HelpEntry(
        func="终末地角色卡片",
        category="endfield",
        command="ef",
        brief_des="查看终末地角色面板与养成状态",
        condition="角色已绑定 · 支持查询他人",
        examples=("ef", "ef -r 2 -s", "sk efcard @某人 -a"),
        detail_des=(
            "### 显示选项\n\n"
            "| 参数 | 作用 |\n| --- | --- |\n"
            "| `-r` / `--role <序号>` | 临时选择自己的终末地角色 |\n"
            "| `-a` / `--all` | 展示全部角色，不使用默认的森空岛配置过滤 |\n"
            "| `-s` / `--simple` | 使用简化背景 |\n\n"
            "快捷指令 `ef` 与 `zmd` 均可使用  \n不带选角时支持通过 @ 或 QQ 号查询他人的默认角色"
        ),
    ),
    HelpEntry(
        func="终末地签到",
        category="endfield",
        command="终末地签到",
        brief_des="签到本人全部终末地角色",
        condition="已绑定用户",
        examples=("终末地签到", "终末地签到 -r 2", "sk efsign sign --all"),
        detail_des=(
            "### 签到范围\n\n"
            "裸快捷指令签到本人全部终末地角色  \n追加 `-r <序号>` 时仅签到所选角色  \n"
            "`efsign sign --all` 也只签到 **本人** 全部角色；`-r` 与 `--all` 不可同时使用\n\n"
            "> 每天 00:20 自动执行终末地签到，结果可通过「终末地签到详情」查看"
        ),
    ),
    HelpEntry(
        func="终末地签到详情",
        category="endfield",
        command="终末地签到详情",
        brief_des="查看终末地签到结果和失败原因",
        condition="已绑定用户",
        examples=("终末地签到详情", "终末地签到详情 -r 2", "sk efsign status"),
        detail_des=(
            "默认展示本人全部终末地角色的缓存签到结果  \n追加 `-r <序号>` 仅查看对应角色\n\n"
            "> `status --all` 是超管查看机器人全部用户的入口，不能与个人选角同时使用"
        ),
    ),
    HelpEntry(
        func="战争回响",
        category="endfield",
        command="战争回响",
        brief_des="查看赛季荣勋、轮换战绩与通关编队",
        condition="角色已绑定 · 支持查询他人",
        examples=("战争回响", "战争回响 -s -1", "sk efwar -r 2 -s 1 -w 2"),
        detail_des=(
            "### 赛季与轮换\n\n"
            "| 参数 | 作用 |\n| --- | --- |\n"
            "| `-s` / `--season <序号>` | 正数按卡片赛季序号选择；负数从当前赛季回溯 |\n"
            "| `-w` / `--week <序号>` | 按卡片轮换序号选择 |\n"
            "| `-r` / `--role <序号>` | 临时选择自己的终末地角色 |\n\n"
            "不带参数展示当前赛季与当前轮换  \n`-s -1` 表示上一赛季"
        ),
    ),
    HelpEntry(
        func="终末地抽卡记录",
        category="endfield",
        command="终末地抽卡记录",
        brief_des="自动更新历史，查看角色池与武器池统计",
        condition="角色已绑定 · 更新需要 token",
        examples=("终末地抽卡记录", "终末地抽卡记录 -r 2", "sk efgacha -b 1 -l 3"),
        detail_des=(
            "### 一条命令完成更新与查看\n\n"
            "自动获取最新记录，去重保存后再展示，无需额外更新指令或 `-u`  \n"
            "追加 `-r <序号>` 临时选择自己的终末地角色\n\n"
            "### 卡池与分页\n\n"
            "`-b` / `--begin` 与 `-l` / `--limit` 分别对 **限定、武器、新手、常驻、联合寻访**"
            "各类别的卡池切片，不改变累计统计  \n长记录会自动分图，累计统计只在首页显示\n\n"
            "> 接口不可用或账号未保存 token 时，仅在已有本地记录的情况下展示缓存，"
            "并明确标记本次未更新；没有本地记录则提示原因"
        ),
    ),
    HelpEntry(
        func="暗语",
        category="interaction",
        command="background / clue",
        brief_des="回复卡片，获取背景原图或线索板",
        condition="回复支持此功能的插件图片",
        examples=("background", "clue"),
        use_prefix=False,
        detail_des=(
            "| 回复内容 | 对应图片 | 结果 |\n| --- | --- | --- |\n"
            "| `background` | 带背景的插件卡片 | 获取背景图片 |\n"
            "| `clue` | 支持线索的方舟角色卡片 | 展示线索板 |\n\n"
            "先引用机器人发送的图片，再发送对应单词  \n并非每一类卡片都提供全部暗语，"
            "引用信息过期后请重新查询卡片"
        ),
    ),
    HelpEntry(
        func="全体签到",
        category="admin",
        command="全体签到",
        brief_des="签到机器人全部用户的方舟角色",
        condition="仅超级用户",
        examples=("全体签到", "sk arksign all"),
        detail_des="面向所有绑定到机器人的用户执行方舟签到，不是个人全部角色签到  \n结果可通过「全体签到详情」查看",
    ),
    HelpEntry(
        func="全体签到详情",
        category="admin",
        command="全体签到详情",
        brief_des="汇总机器人全部方舟签到结果",
        condition="仅超级用户",
        examples=("全体签到详情", "sk arksign status --all"),
        detail_des="查看所有用户的方舟签到缓存结果  \n`--all` 与 `-r` / `--role` 互斥",
    ),
    HelpEntry(
        func="终末地全体签到",
        category="admin",
        command="终末地全体签到",
        brief_des="签到机器人全部用户的终末地角色",
        condition="仅超级用户",
        examples=("终末地全体签到", "sk efsign all"),
        detail_des="面向所有绑定到机器人的用户执行终末地签到  \n个人签到请使用「终末地签到」",
    ),
    HelpEntry(
        func="终末地全体签到详情",
        category="admin",
        command="终末地全体签到详情",
        brief_des="汇总机器人全部终末地签到结果",
        condition="仅超级用户",
        examples=("终末地全体签到详情", "sk efsign status --all"),
        detail_des="查看所有用户的终末地签到缓存结果  \n`--all` 与 `-r` / `--role` 互斥",
    ),
    HelpEntry(
        func="全体角色更新",
        category="admin",
        command="全体角色更新",
        brief_des="逐账号同步机器人全部用户的角色",
        condition="仅超级用户",
        examples=("全体角色更新", "sk char update --all"),
        detail_des="逐个森空岛账号同步角色  \n单个账号失败不会回滚其他已成功账号；不会自动替用户更改已选择的默认角色",
    ),
    HelpEntry(
        func="资源更新",
        category="admin",
        command="资源更新",
        brief_des="更新游戏与卡池数据，不额外下载图片",
        condition="仅超级用户",
        examples=("资源更新", "sk sync --data --force", "sk sync --img --force --update"),
        detail_des=(
            "### 数据与图片分开更新\n\n"
            "快捷指令仅更新数据；裸 `sk sync` 同时更新图片与数据\n\n"
            "| 选项 | 作用 |\n| --- | --- |\n"
            "| `--data` | 仅更新游戏数据与卡池数据 |\n"
            "| `--img` | 仅更新干员立绘、技能图标等图片 |\n"
            "| `--force` | 忽略版本检查，强制检查更新 |\n"
            "| `--update` | 下载图片时覆盖已有文件 |\n\n"
            "选项可组合使用  \n每天 09:00 自动更新数据，沿用 APScheduler 时区，默认 Asia/Shanghai；"
            "可设置 `skland__auto_update_resources=False` 关闭\n\n"
            "> 下载或校验失败保留旧数据  \n> 图片下载是可选操作，不包含在每日数据任务中"
        ),
    ),
    HelpEntry(
        func="自定义指令",
        category="admin",
        command="sk --shortcut",
        brief_des="为常用操作添加自己的快捷指令",
        condition="仅超级用户 · Alconna 快捷指令",
        examples=(
            'sk --shortcut {prefix}兔兔签到 "{prefix}sk arksign sign --all"',
            "sk --shortcut list",
            "sk --shortcut delete {prefix}兔兔签到",
        ),
        detail_des=(
            "### 添加、查看与删除\n\n"
            "添加时依次填写快捷指令与目标命令；包含空格的内容需要用引号包裹  \n"
            "`list` 列出快捷指令，`delete <快捷指令>` 删除指定条目\n\n"
            "> 自定义快捷指令不会自动补上 Bot 的命令前缀，注册时需要填写完整触发词  \n> "
            "示例已按当前 Bot 的一个可用前缀展示"
        ),
    ),
)

HELP_CATEGORIES: dict[str, HelpCategory] = {entry.func: entry.category for entry in HELP_ENTRIES}

extra_data = {
    "menu_data": [entry.to_menu_data(HELP_PREFIX) for entry in HELP_ENTRIES],
    "pmn": {"markdown": True, "template": "skland", "inherit_func_template": True},
}
