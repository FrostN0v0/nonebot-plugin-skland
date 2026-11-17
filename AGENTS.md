# AGENTS.md

本文档为 AI 编程代理（如 Codex、Claude Code 等）提供本仓库的项目上下文与开发指南。内容应以当前源码为准；修改实现后请同步更新本文档。

## 项目概述

**nonebot-plugin-skland** 是一个基于 NoneBot2 的 Python 插件，用于通过森空岛（Skland）及鹰角相关 Web API 查询游戏数据。

当前支持：

- **明日方舟（Arknights）**：角色信息卡片、每日签到、肉鸽战绩与单局详情、卫戍协议生涯与单局战绩、抽卡记录查询、从小黑盒导入抽卡记录、方舟干员查询。
- **明日方舟：终末地（Endfield）**：角色信息卡片、每日签到、战争回响战绩、抽卡记录查询与更新；抽卡统计支持角色池、武器池、新手池、常驻池、限定池、重构角色/武器池、联合寻访池。

## 技术栈与关键依赖

- **Python**: >= 3.10
- **Bot 框架**: NoneBot2
- **命令系统**: nonebot-plugin-alconna / arclet-alconna
- **用户会话**: nonebot-plugin-user
- **数据库**: SQLAlchemy ORM（通过 nonebot-plugin-orm）
- **数据库迁移**: Alembic（通过 nonebot-plugin-orm）
- **渲染**: nonebot-plugin-htmlrender + Jinja2 模板 + Tailwind CSS
- **定时任务**: nonebot-plugin-apscheduler
- **暗语功能**: nonebot-plugin-argot
- **交互等待**: nonebot-plugin-waiter
- **本地存储**: nonebot-plugin-localstore
- **HTTP 客户端**: httpx
- **二维码**: qrcode[pil]
- **测试**: pytest / pytest-asyncio / nonebug
- **代码质量**: Ruff、Pyright、pre-commit.ci
- **包管理**: uv；构建后端为 uv_build

## 目录结构

```text
nonebot_plugin_skland/
├── __init__.py          # 插件元数据、依赖 require、命令处理器注册
├── matcher.py           # Alconna 命令树、别名 sk、Argot/ReplyRecord 扩展
├── hook.py              # 启动/关闭钩子：加载数据、注册/持久化快捷指令、可选资源检查
├── tasks.py             # APScheduler：每日签到与 09:00 数据资源更新
├── config.py            # Pydantic 配置、资源/缓存/数据目录常量
├── extras.py            # 单一帮助目录、命令示例与 PicMenu 元数据
├── model.py             # nonebot-plugin-orm 模型：SkUser、Character、CharacterDefault、GachaRecord
├── account.py           # 多账号角色快照、默认角色投影、角色同步与账号操作互斥
├── db_handler.py        # 账号、角色、默认角色与抽卡记录查询/写入契约
├── data_source.py       # 游戏数据下载、干员目录构建与本地元数据缓存
├── player_data.py       # 玩家实时数据账号级短期缓存：ArkCard TTL/LRU/single-flight
├── image_cache.py       # 方舟半身图浏览器响应缓存与显式资源就绪等待
├── compact.py           # htmlrender 模板、页面与截图兼容适配
├── download.py          # 图片下载与数据专用 GitHub 客户端：提交定位、连接池及代理回退
├── render.py            # HTML 模板渲染为图片的函数
├── filters.py           # Jinja2 过滤器与可复用图片资源 URL 函数
├── exception.py         # Shared API and account-operation errors
├── services/
│   ├── __init__.py      # Package boundary without implicit exports
│   ├── auth.py          # Credential refresh policy and detached credential state
│   ├── garrison.py      # 卫戍资源、当前赛季和账号凭证读取编排
│   ├── binding.py       # Binding preparation and atomic confirmed account mutations
│   ├── gacha.py         # History fetching, grouping, and Heybox conversion
│   ├── resources.py     # 启动、手动、定时数据更新互斥与汇总反馈
│   └── sign.py          # Signing, ordered cache persistence, filtering, and formatting
├── integrations/
│   ├── __init__.py      # 可选集成包边界，不聚合导出
│   └── picmenu.py       # 已加载 PicMenu Next 时注册专属帮助模板
├── utils/
│   ├── __init__.py      # Package boundary without implicit exports
│   ├── background.py    # Configured background selection
│   ├── files.py         # Same-directory atomic publication of single files
│   ├── message.py       # Command reactions and API error feedback
│   └── qrcode.py        # Safe avatar fetching and pixel-preserving QR cards
├── api/
│   ├── __init__.py      # API 模块导出
│   ├── request.py       # SklandAPI：森空岛/抽卡/终末地接口与签名逻辑
│   ├── login.py         # SklandLoginAPI：token、cred、扫码登录相关接口
│   ├── resources.py     # 官方 Wiki 游客设备注册、短期签名与公开武器目录
│   └── dId.py           # dId 获取逻辑（部分接口签名需要）
├── commands/
│   ├── __init__.py      # 命令 handler 导出
│   ├── arksign.py       # 明日方舟签到与签到状态查询
│   ├── bind.py          # token/cred/二维码确认式绑定与交互解绑
│   ├── box.py           # 方舟干员查询、自然筛选与分页发送
│   ├── card.py          # 明日方舟角色卡片查询
│   ├── char.py          # 多账号角色总览、默认角色切换与逐账号同步
│   ├── selection.py     # Shared game-aware role selection and overview feedback
│   ├── gacha.py         # 明日方舟抽卡记录查询、分页、导入小黑盒记录
│   ├── rogue.py         # 肉鸽战绩查询与单局详情
│   ├── garrison.py      # 卫戍生涯、战绩列表、收藏和单局详情
│   ├── sync.py          # 资源与数据同步命令
│   └── endfield/
│       ├── __init__.py  # 终末地 handler 导出
│       ├── card.py      # 终末地角色卡片
│       ├── sign.py      # 终末地签到与签到状态
│       ├── gacha.py     # Endfield gacha history update and paginated rendering
│       └── war_echoes.py  # 战争回响查询与图片发送
├── schemas/
│   ├── __init__.py      # 对外集中导出 Pydantic 模型
│   ├── binding.py       # 森空岛 wire model、确认快照与绑定角色卡 DTO
│   ├── cred.py          # CRED 凭证模型
│   ├── sign.py          # Shared SignResult and sign-cache contracts
│   ├── help.py          # 帮助目录、可见项分组与编号投影
│   ├── arknights/
│   │   ├── card.py      # ArkCard 角色卡片结构
│   │   ├── sign.py      # Arknights sign API response
│   │   ├── game_data.py # 抽卡详情、官方干员目录与 PRTS 元数据快照结构
│   │   ├── operator_query.py # Natural filters, aliases, and query validation
│   │   ├── garrison.py  # 卫戍 wire model、跨版本资源匹配与模板视图
│   │   ├── operators.py # Operator card/module projections and roster ordering
│   │   ├── gacha/       # 明日方舟抽卡基础、卡池、统计模型
│   │   ├── rogue/       # 肉鸽基础数据、生涯统计、历史记录模型
│   │   └── models/      # 角色卡片的状态、干员、基建、招募、活动、皮肤等详细模型
│   └── endfield/
│       ├── card.py      # EndfieldCard 与终末地角色卡片结构
│       ├── sign.py      # EndfieldSignResponse
│       ├── item_icons.py # 官网 HTML/CSS、Wiki 目录与游戏 ID 的图标投影
│       ├── war_echoes.py  # 战争回响 wire model、评级/荣勋与赛季轮换视图
│       └── gacha/
│           ├── base.py       # EndfieldPoolType、角色/武器抽卡响应、Content API 模型
│           ├── pool.py       # EfGachaPoolInfo、保底/歪卡/武库配额统计
│           ├── statistics.py # Cumulative category statistics and pool selection
│           └── view.py       # Complete paid/free events projected before layout
├── migrations/          # nonebot-plugin-orm/Alembic 迁移脚本
└── resources/
    ├── fonts/           # 渲染字体
    ├── images/          # 内置图片资源（背景、职业、稀有度、终末地素材、抽卡装饰等）
    └── templates/       # Jinja2 HTML 模板与生成的 CSS
        ├── ark_card.html.jinja2
        ├── operator_roster.html.jinja2
        ├── operator_roster_macros.html.jinja2
        ├── bound_roles.html.jinja2
        ├── help_overview.html.jinja2
        ├── help_detail.html.jinja2
        ├── help_macros.html.jinja2
        ├── endfield_card.html.jinja2
        ├── gacha.html.jinja2
        ├── gacha_macros.html.jinja2
        ├── ef_gacha.html.jinja2
        ├── ef_gacha_macros.html.jinja2
        ├── ef_gacha.js       # 类别分区、响应式列数与完整事件续页
        ├── rogue.html.jinja2
        ├── garrison.html.jinja2
        ├── garrison_macros.html.jinja2
        ├── rogue_info.html.jinja2
        ├── ef_war_echoes.html.jinja2
        ├── rogue_macros.html.jinja2
        ├── endfield_macros.html.jinja2
        ├── macros.html.jinja2
        └── clue.html.jinja2
```

项目根目录还有：

- `tests/`：nonebug 与真实 API 测试。
- `pyproject.toml`：依赖、NoneBot 插件配置、Ruff/Pyright/Pytest/Bumpversion 配置。
- `package.json`：Tailwind CSS 编译脚本。
- `tailwind.css`：Tailwind 输入 CSS。

业务用例集中在 `services/`，图片和消息工具集中在 `utils/`，不将业务和工具模块平铺到包根目录。两者的 `__init__.py` 不聚合导出；调用方直接导入对应子模块，不使用包根目录兼容转发。

## 命令系统

命令树定义在 `nonebot_plugin_skland/matcher.py`，插件入口在 `nonebot_plugin_skland/__init__.py` 使用 `@skland.assign(...)` 分发到各 `commands/` handler。

主命令：

```text
skland [target] [-r|--role <index>]
sk [target] [-r|--role <index>]    # Alconna alias
```

主要子命令：

```text
skland bind <token|cred> [-u]
skland qrcode
skland unbind
skland arksign sign [--all | -r|--role <index>]
skland arksign status [--all | -r|--role <index>]
skland arksign all
skland efsign sign [--all | -r|--role <index>]
skland efsign status [--all | -r|--role <index>]
skland efsign all
skland char
skland char set <ark|arknights|ef|endfield> <index>
skland char update [--all]
skland sync [--img] [--data] [--force] [--update]
skland rogue [target] [-r|--role <index>] [--topic <topic>]
skland garrison [target] [-r|--role <index>] [-i|--index <record_index>] [-f|--favored] [-a|--all]
skland rginfo <id> [-r|--role <index>] [-f]
skland gacha [target] [-r|--role <index>] [-b <begin>] [-l <limit>]
skland import <url> [-r|--role <index>]
skland box [target] [filters ...] [-r|--role <index>] [-o <owned|unowned|all>] [-ra <rarity>] [-p <profession>] [-b <branch>] [--position <position>] [--gender <gender>] [-f <faction>] [--race <race>] [--potential <potential>] [-s <release|acquired|training>] [-n <name>]
skland efcard [target] [-r|--role <index>] [-a] [-s]
skland efgacha [target] [-r|--role <index>] [-b <begin>] [-l <limit>]
skland efwar [target] [-r|--role <index>] [-s|--season <season>] [-w|--week <week>]
```

内置快捷指令在 `hook.py` 启动时注册，并通过 `nonebot_plugin_alconna.command_manager` 持久化到插件缓存目录的 `shortcut.db`。当前包括：森空岛绑定、扫码绑定、森空岛解绑、森空岛角色、切换方舟角色、切换终末地角色、明日方舟签到、签到详情、全体签到、全体签到详情、各肉鸽主题、卫戍战绩、角色更新、全体角色更新、资源更新、战绩详情、收藏战绩详情、方舟抽卡记录、导入抽卡记录、方舟干员、终末地签到、终末地签到详情、终末地全体签到、终末地全体签到详情、`ef|zmd`、终末地抽卡记录、战争回响。启动加载缓存后会删除缓存中的“终末地抽卡更新”入口。

`森空岛角色` 精确匹配 `skland char`；`切换方舟角色 <index>` / `切换终末地角色 <index>` 分别映射到 `skland char set ark <index>` / `skland char set ef <index>`，使用 `fuzzy=True` 接收序号、`compact=False` 要求空格分隔，并沿用 Bot 的命令前缀。内置快捷指令在加载缓存后注册。

个人签到快捷指令保留裸命令签到全部个人角色的行为；追加选项时由独立的带空白前缀规则转发到 `sign`，支持 `-r` / `--role`，不会隐式叠加 `--all`。签到详情快捷指令也允许追加选角参数。其他按角色查询的中文快捷指令继续透传参数。

### 图片帮助

- `extras.HELP_ENTRIES` 是帮助内容的单一来源，通过 `HelpEntry.to_menu_data()` 生成标准 `menu_data`；保留 26 项功能，管理项使用 `pmn_hidden`。`HELP_PREFIX` 从 Bot 的 `command_start` 选择一个可用前缀，暗语保持不带命令前缀。
- `hook.startup()` 首先调用 `integrations.picmenu.register_picmenu_templates()`；只有 PicMenu Next 已加载时才 `require` 并导入其接口，未安装或未加载时不影响 Skland。注册幂等，不更改依赖、不替换全局首页、不启用 Alconna 全局帮助接管。
- 插件声明 `pmn.template="skland"` 并开启功能模板继承，分别注册总览和通用详情回调；方舟干员通过 `pmn_template="skland_roster"` 使用同一详情模板的速查变体。
- `schemas/help.py` 的 `HelpView` 只处理 PicMenu 实际传入的可见列表与功能正文，按当前列表生成用户可见编号后再分组；未知外部条目归入其他功能，无编号的 Alconna 临时帮助不编造序号。不修改共享菜单模型，也不从原目录恢复已过滤条目。
- Markdown 和 `plugin:self,...` 资源解析复用 PicMenu 的 `build_base_render_kwargs`、`build_default_prp_processor` 与 data URL 转换器；标题及普通文字显式转义。`render.render_help()` 沿用现有 `compact` 边界、资源就绪等待、706px 视口、1.5 倍 PNG 和全局截图超时；`skland-help-*` 样式集中于 Tailwind，不修改其他卡片样式。
- 图片帮助的中文条目、列表及分行说明不使用句末句号；段内多句通过 Markdown 硬换行保持分隔，不在渲染器中全局替换标点，也不修改命令、URL 或版本号中的点号。
- 入口为 `帮助 森空岛` 与 `帮助 森空岛 <功能名称或编号>`，前缀遵循 Bot 配置。`-H` 仅控制菜单可见性，不能代替命令权限；限制普通帮助入口查看隐藏项需配置 `PMN_ONLY_SUPERUSER_SEE_HIDDEN=True`。`sk box --help` 接管产生的正文仍来自 Alconna，不自动映射到手写的方舟干员说明。

## 核心实现说明

### 配置

配置模型在 `config.py`：

```python
class Config(BaseModel):
    skland: ScopedConfig = Field(default_factory=ScopedConfig)
```

`.env` 中使用 `skland__...` 形式配置。当前字段：

- `github_proxy_url`: GitHub 代理前缀，默认 `https://gh-proxy.com/`；显式空字符串保持直连，自定义配置不被覆盖。
- `github_token`: GitHub Token，用于缓解 GitHub API 限流。
- `check_res_update`: 启动时是否检查并下载图片资源。
- `auto_update_resources`: 是否每天 09:00 自动更新数据资源，默认开启；不包含图片。
- `ark_portrait_cache_enabled`: 是否在首次渲染时按需缓存可拼链的方舟干员/皮肤半身图，默认关闭。
- `background_source`: 明日方舟/终末地卡片背景来源，支持 `default` / `Lolicon` / `random` / `CustomSource`。
- `endfield_background_simple`: 是否默认启用终末地角色卡片简化背景。
- `rogue_background_source`: 肉鸽背景来源，支持 `default` / `rogue` / `Lolicon` / `CustomSource`。
- `argot_expire`: 暗语缓存过期时间（秒）。
- `ark_card_cache_ttl`: 玩家角色卡内存缓存时间（秒），默认 120。
- `ark_card_cache_max_entries`: 玩家角色卡内存缓存角色数量上限，默认 64。
- `gacha_render_max`: 明日方舟抽卡记录单图渲染卡池上限。
- `ef_gacha_render_max`: 每张终末地抽卡图片中各类别的不同卡池数量上限，默认 5 且必须为正；分页同时受实际内容高度约束。
- `roster_render_max`: 方舟干员单图渲染数量上限，默认 16。
- `render_timeout`: 所有模板传给 htmlrender 的截图超时时间（毫秒），默认 180000。
- `roster_render_format`: 方舟干员图片格式，支持 `png` / `jpeg`，默认 `jpeg`。
- `roster_jpeg_quality`: 方舟干员 JPEG 质量，默认 90。

资源路径：

- `RES_DIR`: 包内静态资源目录。
- `TEMPLATES_DIR`: 包内模板目录。
- `CACHE_DIR`: `nonebot-plugin-localstore` 插件缓存目录。
- `DATA_DIR`: `nonebot-plugin-localstore` 插件数据目录。
- `GACHA_DATA_PATH`: 明日方舟游戏数据缓存目录。
- `OPERATOR_METADATA_PATH`: PRTS 干员筛选元数据快照路径。

### 数据库模型

`model.py` 中有四个主要 ORM 模型：

- `SkUser`
  - 每行表示一个森空岛账号绑定；自增 `id` 为账号主键，`owner_id` 是所属 NoneBot 用户 ID。
  - 保存 `access_token`、`cred`、`cred_token`、可空 `skland_user_id`；同一 owner 下非空远端账号 ID 唯一。
- `Character`
  - 每行表示一个具体游戏角色，通过 `account_id` 归属森空岛账号。
  - 角色身份为账号、`app_code`、`channel_master_id`、`role_id`；终末地同一 binding UID 下的多服务器角色可并存。
  - `is_skland_default` 仅用于展示和首次默认候选，不直接决定插件查询角色。
- `CharacterDefault`
  - 以 `(owner_id, app_code)` 保存每个 NoneBot 用户在明日方舟/终末地各自选择的插件默认角色。
  - 默认角色属于用户和游戏，而不是某个森空岛账号。
- `GachaRecord`
  - 通过 `character_id` 直接归属具体角色；`item_type` 区分 `char` / `weapon`，`is_free` 标记终末地免费抽。
  - 唯一约束为 `character_id + gacha_ts + pos`，不同账号角色可保存相同时间与位置的记录。
  - 可空 `pool_version` 保存终末地接口 `poolVersion`，用于区分重构池当期期次；旧记录不按池名或时间猜期次，成功同步时按现有记录身份回填，不计为新增抽卡。

账号删除通过数据库/ORM 级联删除其角色、默认映射和抽卡记录。新增或修改模型后需要添加迁移脚本。

多账号升级迁移会丢弃没有对应 `SkUser` 绑定账号的旧版孤立角色缓存并记录警告；抽卡归属错配、缺失角色引用和身份冲突仍会拒绝迁移，避免静默破坏有效记录。

### API 与签名

`api/request.py` 中 `SklandAPI.get_sign_header()` 负责生成森空岛签名请求头。

同模块的私有函数 `_raise_for_skland_code(payload, error_prefix=...)` 为 13 个同类业务接口统一错误码映射：`10000` 为 `UnauthorizedException`，`10002` 为 `LoginException`，其他非零码为 `RequestException`。调用方保留各自的错误文案前缀，每个响应只解析一次 JSON；HTTP、JSON 解码与模型校验仍由各接口处理。登录接口、dId 设备注册及公开资源接口不套用这套账号异常分类。

签名流程：

```text
1. 构造 header_ca：platform、timestamp、dId、vName
2. GET 使用 URL query，POST 使用 JSON body 作为 query_params
3. secret = path + query_params + timestamp + compact_header_ca_json
4. HMAC-SHA256(cred_token, secret) 得到 hex_secret
5. MD5(hex_secret) 得到 sign
```

常用 API 方法：

- `get_binding()`：获取森空岛绑定游戏角色。
- `get_user_ID()`：获取森空岛 userId。
- `ark_card()`：获取明日方舟角色卡片数据。
- `ark_sign()`：明日方舟签到。
- `get_rogue()`：明日方舟肉鸽数据。
- `get_gacha_categories()` / `get_gacha_history()`：明日方舟抽卡类别与记录。
- `endfield_card(cred, *, user_id, role_id, server_id)`：终末地角色卡片数据；API 层只接收标量身份，不依赖 ORM `Character`。
- `endfield_war_echoes(cred, *, user_id, role_id, server_id, season_id=None)`：战争回响赛季、轮换、关卡和荣勋数据。
- `endfield_sign()`：终末地签到。
- `get_ef_gacha_history()`：终末地角色池/武器池抽卡记录。
- `get_ef_gacha_content()`：终末地卡池 UP 内容。

`api/login.py` 的 `SklandLoginAPI` 负责 token/cred 互换、cred_token 刷新、二维码扫码登录、role token 获取等。

`SklandLoginAPI.get_cred()` 在现有非零 `status` 错误分支中读取响应的 `message`，保留服务端错误描述；不改变成功 CRED 解析或认证判断。`tests/test_auth.py` 使用离线 HTTP 传输覆盖错误消息字段，避免拼写错误将失败原因显示为 `None`。

### Token 自动刷新

`services/auth.py` 的 `refresh_credentials` 统一执行凭证刷新；`CredentialState` 用于不持有数据库事务的账号同步。该模块不发送消息，也不使用 `None` 或错误字符串表示接口失败。

- `UnauthorizedException` 触发一次 `cred_token` 刷新；重试若遇到 `LoginException`，允许再用保存的 token 刷新一次 cred。
- `LoginException` 触发一次 cred 刷新；缺少 `access_token` 时立即抛错，不请求 grant code。
- 请求错误、刷新错误和最终重试失败直接向调用方传播，不无限重试。
- 交互命令通过 `utils/message.py` 反馈错误；批量签到在 `services/sign.py` 中将角色失败转换为缓存记录，账号同步返回 `AccountSyncResult`。
- `player_data.get_ark_card()` 的刷新边界保留在每个调用者上下文，位于 single-flight 之外；并发等待者分别保存自己的刷新结果。


### 账号绑定与管理

- 同一 NoneBot 用户可绑定多个森空岛账号；token/cred 仅允许私聊，二维码入口保持群聊可用。
- token、cred 和扫码所得凭证都先调用一次 binding API，渲染确认后的完整账号角色卡；只有命令发起者回复“确认”后才原子写入。
- `services/binding.py` 负责凭证和身份准备、确认快照复核及绑定/解绑的原子提交；`commands/bind.py` 只编排展示、waiter、扫码轮询与撤回。工作状态使用内部 dataclass，跨模块业务异常位于 `exception.py`。
- `account.sync_account()` 使用普通凭证快照执行 API 请求，再重新读取账号并事务性同步角色/默认映射；不构造未持久化的 `SkUser` 充当临时凭证对象。同步保留仍有效的默认角色，清空指向已移除角色的默认映射，由用户重新选择；个人和全体角色更新共用此流程。
- `skland char` 返回全部账号和角色；`skland char set <game> <index>` 按游戏独立序号切换插件默认角色，所有业务功能使用该角色所属账号的凭证。
- 角色卡片、两游戏抽卡查询/更新、抽卡导入、干员查询、肉鸽及详情、卫戍战绩及详情、战争回响、两游戏个人签到及状态共 14 个入口统一支持 `-r` / `--role`。`matcher._role_option()` 为每个作用域构建独立选项，命令分发传入 `role_index`；各 handler 共用 `commands/selection.py` 的 `check_user_character(app_code=...)`，使用角色所属账号、不写 `CharacterDefault`、不要求已有默认角色，也不能临时选择他人的角色。`get_character_by_index()` 与 `char set` 共用 `get_user_characters()` 排序，无效序号不回退默认。
- `skland box -r` 用于角色序号，星级短选项为 `-ra`；`--rarity`、`rarity` 和自然筛选词均可筛选星级。示例和调用必须明确区分角色与星级选项，不能根据值猜测 `-r` 的用途。
- 签到状态不带选角参数时保留本人全部角色结果；显式选角时按 owner 和角色主键共同过滤缓存，防止跨账号、跨用户混入。`--all` 为超管全体状态，与选角互斥；全体签到提交后展示状态时不读取已过期的 `UserSession.user`。
- 肉鸽详情不带选角参数时使用引用图片的缓存数据；显式选角时获取所选角色的新数据，引用图片只提供主题，无引用时使用角色当前主题。肉鸽 API 读取后在渲染前提交凭证刷新；线索、背景等暗语继续沿用原卡片携带的数据。
- 战绩详情编号由 `RogueHistory.select_record(index, favored=...)` 在最近或收藏列表内校验 `1..记录数`；越界或列表为空时提示可用范围，不跨列表回退。`render_rogue_info()` 只接收已选定的记录。
- 个人签到使用 `-r` / `--role` 按角色序号选角；`--role` 与 `--all` 同时出现时拒绝执行。`-u` 仅在 `bind` 中用于更新账号、在 `char` 中作为 `update` 的别名同步角色、在 `sync` 中用于覆盖已有图片；`gacha` 和 `efgacha` 均不接受 `-u`。主卡片 handler 使用选项感知的分发，根 `--role` 与不支持的子命令组合会明确拒绝，避免误触发双 handler。
- 账号角色卡使用本地灰阶纹理、游戏字标与档案式布局；身份资料仅展示昵称、玩家 UID 和区服名称，保留账号/角色选择序号与默认/操作状态，不展示账号尾号、终末地绑定 UID、服务器内部编号或等级。
- 角色选择编号仅显示数字，不在数字下方重复标注“序号”，也不在卡片右下角显示分游戏编号说明。
- `BoundRoleCardItem.player_uid` 对方舟返回 `binding_uid`，对终末地返回 `game_role_id`；内部字段继续保留用于身份识别与确认校验。模板显式开启 Jinja autoescape，避免依赖 htmlrender 默认不转义的环境。
- `BoundRoleCardItem.server_label` 按方舟渠道 ID 将 `1` / `2` 显示为“官服” / “bilibili服”，兼容 `server_name` 保存渠道编号的记录；终末地接口区服名 `China` 显示为“国服”。未知渠道沿用原区服名，不修改数据库、API 请求和角色身份匹配使用的原始名称或服务器 ID。
- `skland unbind` 先选择账号序号或“全部”，再二次确认；删除当前默认角色后清空默认，不自动切换到其他账号。
- `UserSession.user_id` 会读取 `User.id` ORM 属性；解绑及角色选择流程必须在 `rollback()` / `commit()` 前保存普通整数身份，后续确认、错误反馈与提交后总览不得重新读取已过期的用户 ORM 属性。渲染和 waiter 期间不持有数据库事务。
- `utils/qrcode.py` 保留安全头像下载、原生黑白点阵、M 级纠错和 4 模块静区；命令约 100 秒后撤回二维码。扫码者身份不能由插件验证，最终绑定以命令发起者确认的角色卡为准。

### 玩家角色卡短期缓存

- `player_data.py` 的 `ArkCardDataSource` 为 `commands/card.py`、`commands/box.py` 和 `commands/gacha.py` 统一缓存无副作用的 `ArkCard` API 读取；`get_ark_card()` 在每个命令请求上下文独立执行 token 刷新。
- 缓存按森空岛账号、应用、服务器、角色 UID 与 role ID 隔离，使用绝对 TTL、固定容量 LRU 和同角色 single-flight；命中不会延长过期时间。
- 默认 TTL 为 120 秒、容量为 64，可通过 `ark_card_cache_ttl` 和 `ark_card_cache_max_entries` 配置；只缓存成功解析的 `ArkCard`，异常与空结果不缓存。
- 三个命令在读取完成后、任何提前返回或渲染发送前提交 session，确保自动刷新的 `cred` / `cred_token` 不因后续空结果或发送失败而回滚。
- 角色绑定同步或解绑后会失效对应森空岛账号的缓存；旧的并发请求完成后不会重新写入已失效代际。切换默认角色无需失效缓存。

### 游戏数据与资源

`data_source.py`：

- `GachaTableData`
  - 管理明日方舟 `gacha_table.json`、`character_table.json`、`char_patch_table.json`、`uniequip_table.json`、`handbook_info_table.json`、`handbook_team_table.json`、PRTS 卡池详情与干员筛选元数据。
  - 使用数据专用 `GitHubDataClient` 获取一次上游提交 SHA，再直接下载该提交下六份已知路径 JSON；不获取 GitHub 文件树。远端和本地版本统一去除首尾空白，同版本且本地有效时不重复下载六份表。
  - 下载结果先完成结构、模型和 `OperatorCatalog` 校验，再暂存、逐文件原子替换并在最后写入版本标记；全部成功后才切换内存数据。批次写入失败会在进程内回滚，不承诺多个路径在进程崩溃时仍具有事务原子性。
  - PRTS Cargo API 只补充职业分支中文名、性别和种族；验证后原子保存 `operator_metadata.json`，失败保留旧快照，无快照时使用官方档案。PRTS 卡池详情另存 `DATA_DIR/gacha_details.json`，下载失败保留已验证的磁盘和内存缓存。
  - `load(force=False, refresh_metadata=False, *, client=None)` 可借用共享客户端，返回是否实际持久化了变更。必需更新失败时先恢复可用冷缓存再抛出 `RequestException`，不能把缓存回退报告为“已是最新”。
- `EfGachaPoolTableData`
  - 从 `FrostN0v0/EndfieldGachaPoolTable` 拉取 `GachaPoolTable.json`。
  - 通过相同客户端定位上游提交，直接获取该提交的卡池表；解析验证成功后才替换文件。同语义内容（包括强制检查）不重写缓存；失败保留可用旧数据并抛错。
  - 提供 `get_pool(pool_id)` 为终末地抽卡渲染补充 UP 信息。

- `EfItemIconData`
  - 运行时唯一数据文件是用户配置的 `DATA_DIR/endfield/ItemIconTable.json`，由启动、手动和每日数据更新在本地构建；不维护仓库映射 JSON，不从 GitHub 下载头像表，也不使用随包快照。
  - 角色名称和官网 key 取自 `/operator` 的 SSR HTML，头像完整 URL 取自该页面当前引用 CSS 的角色切换器规则；不执行官网 JS，不推导名称或图片哈希。
  - 武器图标取自森空岛官方 Wiki 公开目录。`api/resources.py` 使用现有 dId 正常设备注册与 `/web/v1/auth/refresh` 返回的游客短期签名 token，不读取玩家凭证、不复用账号刷新流程、不依赖浏览器。
  - 官网页面、样式表及 Wiki 请求不跟随重定向，避免已校验的官方地址跳转到未授权目标；设备注册响应、`detail` 和 `deviceId` 类型异常统一抛出 `RequestException`，由资源更新汇总失败并保留旧表。
  - `schemas/endfield/item_icons.py` 使用现有卡池 `all` 的名称关联游戏 ID；同 ID 的历史名称作为候选别名，只接受唯一官方图片结果。两类资源完整构建并通过官方 HTTPS 域名校验后才原子写入 localstore；等价结果即使 `--force` 也不重写，失败保留旧缓存并报告失败。
  - `filters.ef_item_icon_url()` 统一服务六星、五星汇总和 UP 小图；未收录项保留名称，不拼接第三方地址。数据更新只构建 URL 表，不批量下载图片。

`services/resources.py` 的 `update_data_resources()` 为启动、手动及每日任务提供共用入口。两游戏数据共用一个 `GitHubDataClient`，终末地图片表使用独立官方 HTTP 连接；三项更新独立反馈失败并返回汇总。进程内已有更新时抛出 `ResourceUpdateInProgress`；命令提示稍后重试，定时任务则跳过，不并发写同一组文件。`hook.py` 启动使用此入口加载数据，并在加载快捷指令缓存后将“资源更新”替换为 `skland sync --data`，使用 `compact=False` 要求参数前有空格。

互斥仅覆盖进程内，不提供多进程共享 `DATA_DIR` 时的更新协调。卡池与图标表独立发布，不因图片目录不可用阻止卡池更新；更新期间缺少图标时沿用名称回退，不要求两张表具有联合快照一致性。

数据更新结果保留独立、带 `✅` 的 INFO 日志：干员筛选元数据包含条数，明日方舟游戏数据包含版本，终末地卡池数据包含卡池数，终末地图片资源包含角色数和武器数；不能用英文 DEBUG 替代这些可见结果，也不合并成一条“启动数据资源更新”汇总。

用户侧数据更新回复保留状态图标：更新成功使用 `✅`，已是最新使用 `📦`，更新失败使用 `❌`。终末地卡池表成功或已是最新时返回当前卡池数，统一图片资源表返回角色数和武器数；仍在命令结束后合并发送一条结果消息。

`GitHubDataClient` 默认经配置代理获取 GitHub 数据；原站回退、瞬时故障的有限重试和连接池限流属于单轮更新。失效代理不会让后续文件重复等待相同长超时，GitHub Token 仅传给直连官方 API。PRTS 地址不加 GitHub 代理。此客户端不使用 jsDelivr，也不需要额外镜像仓库或 CI。

数据下载并发上限固定为内部常量 8，不提供用户配置。数据文件流式读取时复用现有 `DownloadProgress` 面板，显示文件名、下载量、速度及响应提供总长度时的百分比；下载开始和完成沿用现有日志风格。首次没有数据缓存是正常初始化，不记录警告；已有缓存无法解析或缺损时仍给出警告，真实下载失败继续报告失败并保留旧数据。

下载框使用临时显示，仅在有实际下载任务时启动，最后一项结束或异常退出时立即清除并恢复光标。框活动期间默认 NoneBot 控制台日志经同一 Rich Console 输出，保留格式、等级和换行；结束后恢复普通控制台输出，不修改其他自定义或文件日志处理器。非交互终端与重定向输出仅输出普通日志，不产生下载边框和光标控制序列。默认控制台处理器被用户替换或已有其他 Live 窗口时，不接管自定义处理器，也不维持第二个下载框。

若 `check_res_update=True`，启动调用 `download.download_img_resource()` 检查图片；手动 `skland sync` 同时更新图片与数据，`skland sync --img` 仅更新图片。图片版本检查、成功/失败计数、已有文件的跳过/覆盖和并发控制由 `download.py` 的图片下载流程负责，与数据更新流程分开。每个图片先写入同目录临时文件，完整下载后原子替换；任一文件失败时不推进图片版本，`sync` 回复失败，下次运行重新下载缺失文件。单文件原子写入统一使用 `utils/files.atomic_write()`，签到缓存与半身图缓存共用同一实现；多文件批次仍由 `data_source._publish_files()` 负责。

卫戍的 45 张固定 UI 和 18 张称号原图随包放在 `resources/images/garrison/`，由 `filters.garrison_asset_url()` 返回文件 URI。新装插件不执行 `sync --img` 也能显示这些素材，运行时不依赖 ArknightsAssets2、本机解包目录或额外数据目录授权。不再维护逐图清单、清单加载器和卫戍专用批量下载分支；`download_img_resource()` 与 `sync --img` 只保留原来的图片下载流程，不清理用户已有资源缓存。

Boss 头像由 `filters.ark_enemy_icon_url()` 按有效敌人 ID 拼接 `yuanyan3060/ArknightsGameResource/main/enemy/` 路径，保留 GitHub 代理配置，不受名称映射名单限制。策略、盟约中央图案和装备继续使用接口直接返回的 `icon`，能力保留 `icon` / `eventTypeIcon`，不新增能力列表或下载任务。既有角色头像、技能、半身图及其缓存目录不变，不增加渲染时自动落盘、Boss 预下载、PRTS 取图或全局图片失败策略。

### 抽卡记录

明日方舟：

- `commands/gacha.py` 编排查询与持久化，`services/gacha.py` 负责分页读取、分组及小黑盒导入转换。
- `services.gacha.group_gacha_records()` 按卡池与时间戳分组，并补充 UP 干员、开放时间、卡池规则类型。
- `render.render_gacha_history()` 使用 `gacha.html.jinja2` 渲染。
- `-b` / `-l` 先按 Python 切片规则规范化为绝对起止位置；超过 `gacha_render_max` 时在该区间内分页，末页不超过用户终点，QQ 合并转发标题使用同一页边界。
- 新记录在查询角色资料前加入 session，并随凭证刷新一起提交；角色资料、渲染或发送失败不会丢失已获取的记录。
- 小黑盒导入按官方角色表解析干员名称（保留夜刀别名），存在无法识别的名称时抛出 `UnresolvedGachaCharacterError`，整次导入不保存并向用户列出名称；未知卡池仍归入 `NORM_1_0_1` / 未知寻访。
- 卡池统计中的平均值为全部六星（含歪卡）的平均抽数，模板标注为 `6★平均`。

### 方舟干员

- 唯一用户快捷入口为 `方舟干员`，映射到 `skland box`；`fuzzy=True` 允许追加参数，`compact=False` 强制筛选词之间使用空格。启动加载快捷指令缓存后会删除缓存中的 `干员盒` 和 `图鉴` 入口。
- `matcher.py` 使用 `MultiVar(str, "*")` 接收任意数量的自然筛选词；QQ 号或 @ 目标位于筛选词之前，裸数字不作为星级或潜能。
- 星级自然筛选与 `-ra` / `--rarity` 共用 `_parse_stars()`，仅在星级入口将中文一至六转换为 1–6，再交给 `_parse_levels()` 处理列表、区间及范围校验；支持 `六星`、`六★`、`四-六星` 和混合数字区间。不会全局改写名称或潜能，连续的 `四五六星` 不代表星级列表。中文与数字等价测试还须断言固定的预期星级集合，避免两条路径都退回默认值时误通过。
- `commands/box.py` 将自然筛选词和高级 Options 一次性交给 `OperatorRosterQuery.from_input()`，不维护两套筛选路径；结果按 `roster_render_max` 分块并发渲染，QQClient 使用合并转发，其他平台逐图发送。
- `schemas/arknights/operator_query.py` 统一解析持有状态、星级、职业、分支、部署位置、性别、势力、种族、潜能、名称和排序。相同集合维度合并为 OR，不同维度为 AND；冲突的持有状态、排序和名称直接报错，无法识别的连写词提示使用空格。
- `schemas/arknights/operators.py` 的 `OperatorCard`、`OperatorModule`、`OperatorRoster` 负责玩家数据合并和排序，单向依赖查询模型；API 中存在但本地目录尚未收录的持有干员通过 fallback 条目保留。
- `Character.potential_level` 将 API 的 `potentialRank` 0-5 转为用户可见的潜能 1-6。练度排序依次比较精英阶段、等级、专精总和、专三数量、已解锁模组最高/总等级、技能等级和信赖，不包含潜能。
- 实装排序使用官方目录 `sort_id`，获取排序使用 `gainTime`；`all` 使用获取或练度排序时先排列已拥有干员，再将未拥有干员按实装顺序放在末尾。`unowned` 不允许潜能、获取或练度条件。
- `schemas/arknights/game_data.py` 从官方数据构造稳定目录，并以 PRTS 快照补充职业分支中文名、性别和种族；阿米娅各职业形态保持独立身份。
- `filters.py` 统一提供立绘、技能、潜能、精英阶段、职业、稀有度、模组及 Half 卡片装饰资源 URL。
- `image_cache.py` 仅在 `ark_portrait_cache_enabled=True` 时登记 `char/portrait` 与 `char_skin/portrait` 拼链资源。首次 HTML 仍保留远程 URL，Chromium 正常并发加载；成功的 `requestfinished` 响应经校验后原子写入 `CACHE_DIR/portrait`，后续渲染由 URL helper 返回本地 URI。不会额外发起图片请求或重新生成 HTML，接口直接返回的图片 URL 不参与缓存。
- `render.render_operator_roster()` 使用 `load`、`document.fonts.ready` 与图片 `decode()` 显式判断资源就绪；远程背景通过隐藏图片节点纳入等待。每页使用独立 BrowserContext、固定 706px Playwright 视口、1.5 设备缩放和可配置截图超时，默认输出 JPEG 90，可配置切回 PNG。
- `operator_roster.html.jinja2` 维护 706px、4 列固定网格；干员卡展示 schema 提供的全部模组；筛选标签支持自动换行，样式编译到 `resources/templates/index.css`。

终末地：

- `services.gacha.sync_ef_gacha_records()` 并发获取 `STANDARD`、`SPECIAL`、`BEGINNER`、`JOINT`、`RERUN` 和 `WEAPON` 六类记录，全部获取成功后按现有角色身份去重（包括同批响应内重复项）、回填已知期次并提交，再返回脱离 ORM 的统计数据。获取失败不保存不完整的新记录，也不提交期次回填。
- 武器抽卡响应中的 `kind="gift_weapon"`、`kind="gift_weapon_box"` 等是赠礼元数据，不具备普通武器记录所需字段；解析时过滤，不计入抽数、保底或数据库，并保留原始末项序号作为分页边界。
- 角色抽卡响应只接受显式 `kind="draw"` 的条目，缺失 `kind` 的事件仍参与原始分页边界但不进入抽卡列表；仅武器旧格式允许省略 `kind`，不能将这项兼容扩展到角色接口。
- `skland efgacha` 和“终末地抽卡记录”统一完成获取、保存和展示，不接受 `-u`，也不提供独立的抽卡更新快捷指令。缺少 token 或接口失败时，仅在已有本地记录的情况下回退，并明确标注记录未更新；错误反馈不包含可能携带凭证的原始请求 URL。
- `SklandAPI.get_ef_gacha_history()` 在 API 边界将 JSON/字符解码错误、非对象响应或 `data`、Pydantic 模型校验失败转换为 `RequestException`，不在错误文案中附带原始响应或请求 URL。登录和鉴权错误保持原异常类型；命令复用已有的文字提示或带未更新标记的缓存展示，不笼统捕获程序、数据库及渲染异常。
- `commands/endfield/gacha.py` 在事务结束前保存普通角色/账号身份，渲染使用脱离 ORM 的数据。头像请求失败不阻断已保存历史的展示，刷新后的凭证在渲染前单独提交；全部图片发送成功后才标记完成。
- `services.gacha.get_all_ef_gacha_records(server_id, ...)` 在每个类别内顺序跟随原始末项 `seqId`；不同角色池共享且不连续的序号不能按页大小推算，只有奖励事件的页面也必须继续。游标缺失或未向前推进时抛出 `RequestException`，不返回部分成功数据；函数不依赖 ORM `Character`。
- `services.gacha.group_ef_gacha_records()` 将记录分为 `beginner_pools`、`standard_pools`、`special_pools`、`rerun_pools`、`joint_pools`、`weapon_pools`。`EfGachaPoolInfo.pool_category` 是唯一分类来源，武器物品类型优先于 ID 前缀，保留历史 `wepon` 命名；重构武器不进入角色统计。
- `EfGroupedGachaRecord` 负责总抽数、六星平均抽数、保底、UP/歪卡与武库配额。限定池、重构角色池或武器子类别任一卡池缺少 UP 信息时，相应类别歪卡数和 UP 平均均为 `None`，模板显示 `-`；各平均抽数只以付费六星为分母（UP 平均为付费 UP 六星），分母为零时为 `None`。
- `EfGachaView.categories` 按限定、重构角色、普通武器、重构武器、联合、常驻、新手生成七个展示类别；普通/重构武器分开计算类别统计，全局武器合计仍涵盖两者。`-b` / `-l` 对每个展示类别独立切片，累计统计不随切片改变。每个 `EfPoolView.periods` 在布局前保留完整付费六星事件与免费批次，重构池按真实 `pool_version` 分段，未知期次单列；同秒不同期不混合，五星汇总不串期，角色出货间隔不因期次分段归零。
- 重构角色的 80 抽小保底仅在所有重构角色池之间共享；同名池的首次 120 抽 UP 保证只生效一次，30/60/90 次付费寻访分别解锁一次免费十连，每 240 次付费寻访达成一次 UP 信物奖励，均按同名池跨期累计。免费抽既不推进保底/奖励，也不因免费六星重置付费保底。
- 重构武器按实际每十件 draw 还原申领批次，不以序号间隙或最大序号计数；4 次申领六星小保底只在当期有效，首次 8 次申领 UP 保证在同名池仅生效一次。累计第 10 次申领达成补充武库箱、第 18 次达成 UP 武器，此后每 8 次交替，累计奖励跨期继承。未知期次不能默认为当期；若计算窗口遇到未知期次且尚无已知六星重置或期次边界，当前保底未知。残缺批次对应累计进度也未知。
- `EfPoolView.rerun_progress` 只投影同名池累计付费、首次 UP 保证、免费十连及奖励门槛，`reward_remaining` 在 schema 中计算；不冒充实际领取台账，UP 信息未知时不推断首次保证状态。类别共享垫抽属于 `EfCategoryView`，武器当期保底属于 `EfPeriodView`；不存在“全部武器共享最新池保底”。逐条六星条仍显示出货间隔抽数，与重构武器按申领次数计算的保底分开。
- `render.render_ef_gacha_history(EfGachaView)` 返回有序 PNG 列表，固定 800px 宽、单页逻辑高度不超过 1600px；类别独立分区，分区内按可见池数使用一至三列，单池使用左侧系列信息、右侧明细的宽卡。同类卡池按最近记录顺序依次放入最短列，不跳过较大的池。每页每类限制不同系列数，续期/续段不重复计池；短池保持完整，超长池才沿完整事件续段，续段仅保留紧凑池名和期次头，不重复横幅及系列奖励摘要。累计统计仅首页展示。
- `schemas/endfield/war_echoes.py` 负责评级、荣勋、最高通关难度、相对赛季选择和用户信息投影；`-s -1` 表示上一赛季，负数先从默认响应解析真实赛季 ID，再请求该赛季详情。命令提交凭证刷新后再渲染脱离 ORM 的视图。

### 卫戍协议战绩

- `skland garrison` 和快捷指令 `卫戍战绩`、`卫` 共用入口，默认只返回首页；`-a` / `--all` 显示所选列表的全部可用战绩，`-i` / `--index` 查看单局，`-f` / `--favored` 在收藏列表内查询和编号，`-r` / `--role` 沿用方舟选角权限。两种快捷指令均沿用 Bot 命令前缀，使用 `compact=False` 要求参数以空格分隔，短入口不匹配其他以“卫”开头的词。不再提供 `--activity` 或手动活动选择，`-a` 不接收活动 ID。列表为空或编号越界时明确提示，不跨战绩和收藏列表回退；单局编号不受默认首页范围限制。
- `SklandAPI.ark_garrison()` 与 `ark_garrison_resources()` 分别读取官方 `/api/ms/game/arknights/garrison/info`、`/resource`，不设置 `x-transformed`，直接解析 `data` JSON 对象，不保留 Base64 解码分支。业务错误先按统一认证分类处理，再检查 HTTP 状态和对应 Pydantic 模型；格式失败统一为不含原始响应或 URL 的 `RequestException`。
- `services/garrison.py` 顺序读取资源和角色战绩，命令自动从资源首个版本获取当前 `activityId`，不硬编码赛季。两次读取共用有界凭证刷新；命令在任何视图构造、图片渲染和消息发送前提交刷新结果，并仅使用已保存的普通 UID、区服、渠道 ID 和脱离 ORM 的模型。`GarrisonView.from_data()` 按角色渠道 ID 将 `1` / `2` 显示为“官服” / “bilibili服”，兼容区服名仍保存编号的旧数据，未知渠道保留原名称；不修改数据库或请求身份，模板继续显式开启 autoescape。
- `schemas/arknights/garrison.py` 负责生涯统计、模式/胜负、品质、策略、盟约、装备、能力和称号投影。生涯场次、胜负和奖杯读取 `career` 字段，零分母胜率未知；记录按实际活动和版本匹配资源，缺元数据保留名称或 ID，不套用最新版本。详情由同一次 `info` 的 `history.records` / `favourRecords` 选择，不额外猜测详情或分页接口，也不执行收藏写操作。
- `GarrisonStrategyStat` 的 `recent_count`、`recent_wins` 和 `win_percent` 统一使用所查询活动中同一策略的场次，继承的 `count` 保持为空，不混入 API 生涯前三次数。`GarrisonBondStat.recent_count` 为激活场次，同局同盟约最多计一次，`max_layer` 取全部已激活条目的最大层数并保留 `0`。偏好、Boss 击杀及游戏时长统计所查询活动的 `history.records`，按记录 ID 去重，不合并收藏、不随选中详情或分页改变。界面使用“战绩记录”“共 N 场记录”等表述；`recent_*` 是现有内部字段名，不是接口时间范围或数据完整性的依据。
- “游戏时长”取同一活动记录的 `gameEndTs - gameStartTs` 总和，先合计秒再显示时分；无记录或任一记录时间缺失、逆序时显示未知，不显示部分合计。统计面板不展示蚀刻章获取及独立／联合高难完成数，改为展示 Boss 击杀总数与其中的隐秘子项；只累计 `acBossInfo.isKilled=True`，隐秘子项另要求 `isHidden=True`，不根据整局胜负推断。无记录为未知，有记录但无击杀为零，原始 wire 字段仍保留。
- `render_garrison_history(props, *, show_all=False)` 的总览固定使用 706px 竖版，每图最多 4 条记录；默认仅渲染首页，`show_all=True` 才渲染全部分页，页码分母始终保留所选列表的总页数。不在统计或单局选择之前截断原始记录，默认首页不会改变生涯及战绩统计；不再保留横版 `layout` 参数或样式分支。生涯概览的六项指标固定两行三列，完整生涯区位于战绩之前且仅首图显示，续图使用紧凑页头。单局详情使用 1080px 视口，8 人及以下按四列展示，9 人及以上按五列换行。模板与浏览器视口共用 `page_width`，沿用 1.5 倍 PNG、资源显式就绪等待及全局截图超时。QQClient 多图按每条合并转发最多 16 张图片顺序分批发送，节点页码在全部图片内连续，仅首批引用原消息；单图及其它平台保留普通图片发送。任一批次失败时停止后续发送，全部批次成功后才标记完成，不自动重发已成功批次。页面保持同一深色圆角外框，模板显式开启 autoescape，新样式只使用 `garrison-*` 命名空间，不新增数据库表、玩家历史文件或配置项。
- 卫戍模板沿用方舟卡片的深色面板、Bender / Akrobat 字体与现有阴影，青绿表示模拟完成，红色表示中断。列表的干员卡宽度上限为 72px；列表和详情均在 8 人及以下按四列展示，9 人及以上按五列完整换行，两者共用半身图与紧凑标识，不截断阵容。`GarrisonOperator.half_portrait_url` 复用 `charId_to_portraitUrl` 的官方角色 ID 资源，不再拼接猜测的 `#1` 皮肤编号；阿米娅职业形态同样使用其自身角色资源。精英化使用 `ark_card/elite/` 素材，技能复用 `ark_skill_icon_url()`。装备位于立绘下方，区域固定宽高比 2:1：不超过两件时保留双槽，更多装备改为两行、按数量增加列数并缩小图标，六件为三列两行，不撑高卡片、不覆盖立绘、不截断装备。列表策略位于回合数右侧，规程与 Boss 位于其下，不再为策略单独预留一行；本局盟约单独分区、全宽排列并保留现有图标及层数大小。
- 干员精英化图标按 `rank_label` 区分普通白色与精锐金色微光，等级数字继续保留；未知品质不染金。精锐身份沿用 `chessInfo.id == goldenChessId` 的非空匹配，不凭 `evolvePhase == 2`、等级或 `mergeLevel` 判断；真实记录存在 `mergeLevel=0` 的精锐干员。`mergeLevel` 只保留 wire 字段，不再投影或显示 `×N` 合成数字角标；列表和详情共用同一干员组件。
- 卫戍随包基础素材包括 `common_logo.png`、`settlemen_personal_success.png`、`settlemen_personal_fail.png`、`operator_lv_bg.png`，原图来自游戏 `autochess/[uc]autochessouter/settlegame/auto_chess_settle_game_state/`。盟约圆盘 `img_bond_bkg.png` 来自 `[uc]autochessouter/stageinfo/stageinfogroup/`，计数底纹 `matte_num.png` 来自 `[uc]autochessbattle/hud/autochess_hud_bond_item/`。圆盘保持 0.8 亮度、图案保持近黑色，在原生纹理外补单一较亮绿色细环，不整体提亮或增加大范围辉光；未激活时连同外环置灰。素材直接读取 `resources/images/garrison/`，图标和底纹均参与资源就绪等待。
- 称号 `comment_icon_*.png` 原样取自 `[uc]autochessouter/arts/titleicon/`，随包放入 `garrison/titles/`，不再拼接森空岛称号 CDN。schema 只接受已随包的 `comment_icon_[1-6]` 和 `comment_icon_[1-6]_[0-2]`：生涯先用条目 `picId`，缺省才回退当前资源；只有计数字典时从资源取 `picId`。单局使用该记录活动/版本的元数据，列表和详情均可显示称号图标；未知或非法 `picId` 保留名称和计数，不从称号编号猜图，不跨活动取图。
- 生涯称号拆为 `normal_titles`、`special_titles`、`other_titles`，不再使用扁平的 `titles`。优先保留 API 普通／特殊列表的分类与零计数；仅有 `titleCntInfo` 时，按经过白名单验证的 `picId` 后缀 `_0`、`_1/_2` 分入特殊、普通，无法确定的条目归入其他称号，不丢弃或按名称猜测。六维评价固定为资金管理、补救能力、领袖挑战、盟约理解、人力调度、装备活用，只使用 `career.titleTypeCnt`，缺失值显示未知；六维全部已知才绘制雷达面积，几何布局留在模板。
- 模式与规程等级使用随包 `garrison/modes/img_title_mode_*.png` 整条原生底图，原图来自 `[uc]autochessbattle/arts/modeinfotitle/`；左侧图形与右侧文字区按原图叠合，不再使用独立的小难度图标。按接口 `modeDifficulty` 的 `FUNNY`、`NORMAL`、`HARD`、`ABYSS`、`FAST`、`TRAINING` 选择，保留 `mode` 的实际文字和规程数字；最佳记录也使用此映射。运行时不根据中文编号推断难度，极速模式不按模式 ID 的 `funny` 后缀误判；未知难度只显示原文，不使用奖杯等级图冒充规程徽章。
- 常用策略和常用盟约各展示最多五项，分别按使用场次、激活场次降序排列，同次数保留接口记录内首次出现的顺序；空 ID 不参与，未知非空 ID 保留名称回退，不按盟约类型排除，也不从生涯前三、徽章或特殊策略补位。偏好区域以五列紧凑横排展示场次、名称及胜率／最高层数，不重复显示场次。`bandBadges` 只提供已有条目的标识：`masterVictor=False` 使用 `title_team_logo_victor.png`，为真使用 `title_team_logo_master.png`，缺记录不显示。单局沿用所查询活动的生涯策略标识，不根据本局胜负推断或跨活动套用，原图保留完整叠层位置。
- 单局头像旁显示原生奖杯段位、结算后的 `trophyAfter` 和本局 `trophyAfter - trophyBefore`，保留零或负变化，不以生涯总数替代历史总数。段位图来自 `[uc]autochessouter/arts/medalicon/trophy_level[1-8]_icon.png`，门槛为 `10、30、60、100、150、200、300`，与官方 `5337.df086ed0.js` 模块 `17524` 的奖杯函数一致。头像名字底纹使用结算页 `id_info_bg.png`，底部统计不再重复展示奖杯变化。
- 干员阶级使用随包 `garrison/tiers/chess_level_icon_[1-6].png`，原图来自 `[uc]autochessouter/arts/chesslevelsprite/`，按 `chessLevel` 选择；超出已知范围保留数值。奖杯与日期分别使用结算页的 `id_info_cup_icon.png`、`date_icon.png`，点赞使用结算玩家项的 `like_icon.png`。击杀数直接使用 `killCnt`，放在通过回合和领袖旁的紧凑信息区，不再单独占据底部大统计框；没有已确认的击杀图标时保留文字。`syncCnt` 仅保留原始 wire 字段，不投影或显示为“调度”等未经确认的统计名称。
- 单局布局按游戏结算页组织：策略头像与模式、胜负横向组合，回合、领袖、击杀和花费金币紧邻，玩家头像与奖杯区置于左下；右侧八人按四列两排展示，九人按五列两排展示，盟约位于阵容下方。花费金币直接使用 `coinCost` 投影的 `record.coin_cost`，零值保留，不恢复独立的大统计块。本局盟约按 `layer` 稳定降序，同层数保留接口顺序，不另按激活状态排序或修改原始记录，列表和详情共用排序视图；偏好榜另按激活场次排名。协防、调和、独行、绝技等继续按接口显示零层，不维护隐藏零层的例外名单。
- 列表显示本局用时，单局底部信息行显示本局用时、开始与结束时间，保留原有时间戳格式；时钟使用结算页 `time_icon.png`。用时由 `gameEndTs - gameStartTs` 计算，跨小时完整显示；缺少有效开始时间或结束早于开始时标注“未提供”，不猜测时长。
- 领袖使用该局活动和版本的 `bossInfo` 解析 `bossId`，优先采用 `handbookEnemyId`，缺少时才用 `enemyId`；不会用当前赛季覆盖历史领袖。`schemas/arknights/garrison.py` 的 `_BOSS_NAMES` 只提供已知名称，不限制头像取图；未知身份保留原始 ID，有效敌人 ID 仍按上游路径拼图，空身份不拼图，不套用其他领袖或维护永久缺图黑名单。当前名称来自 [固定版本敌人图鉴](https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/6f63c14e27b847ef74b53b00fe51fc322b3cd7ff/zh_CN/gamedata/excel/enemy_handbook_table.json) 的 `enemyData[id].name`，头像使用 `ArknightsGameResource` 的 `enemy/` 原路径，不随包复制。
- 列表与单局均展示领袖头像和名称，通过 `round_info_boss_icon.png` / `round_info_boss_icon_sp.png` 标识普通领袖 / 隐秘核心领袖，继续使用 `round_info_boss_bg*.png` 与 `round_info_boss_complete*.png` 原生框和击败标记。`GarrisonBoss.is_hidden`、`is_killed` 分别沿用 `isHidden`、`isKilled`，不解析显示文案选择素材，也不根据整局胜负推断击败状态。`tests/test_garrison_models.py` 覆盖历史身份、领袖状态、常用前五及稳定并列、策略徽标与胜负隔离、奖杯门槛、称号 `picId` 优先级及非法值、难度与未知阶级、盟约层数稳定排序和时间边界。
- 生涯回归覆盖战绩的活动隔离与去重、策略胜率分母、盟约同局激活去重及零层、Boss 总数与隐秘子集、累计用时缺失／逆序、称号分类和六维缺失值。半身图回归固定验证官方角色身份资源，包含阿米娅职业形态，不用皮肤 helper 的返回值互相比较来掩盖错误路径。真实预览提供完整总览及完整单局图，检查六项统计的 3×2 布局、列表和详情的八人四列两排／九人五列两排、列表策略与回合并排且 Boss 位于下方、六件装备在原面积内三列两行、角色及装备不丢失、列表干员和盟约尺寸不变、绿色外环与层数，以及全部图片／字体、金币零值和续页顺序；总模拟数继续取 `career` 的场次字段。

### 渲染系统

渲染入口在 `render.py`。一般模板沿用 `cached_template_to_pic()`；终末地抽卡通过 `compact.open_html_page()` 建立自定义页面，业务模块负责资源就绪等待与 DOM 分页。普通截图和自定义页面均沿用全局 `render_timeout`。

`compact.py` 是唯一 htmlrender 兼容边界，支持最低 0.6.5 至 0.8.x，统一提供模板生成、普通截图和自定义页面接口。0.8.x 使用插件私有 Application 授权 `RES_DIR`、`CACHE_DIR`，不授权整个 `DATA_DIR` 或旧卫戍资源数据目录，按上游资源策略处理本地资源；可复用共享 Playwright，但不得由插件关闭。响应缓存、资源就绪等待和 DOM 分页保留在各自业务模块。

兼容层不得修改全局 Application、全局授权或浏览器安装流程，也不在运行错误后切换 API 分支。插件关闭后拒绝新渲染请求；文件 URI 统一使用 `Path.as_uri()`。

主要函数：

- `render_ark_card()`：明日方舟角色卡片。
- `render_bound_roles_card()`：多账号角色总览、绑定确认和解绑选择/确认卡片。
- `render_operator_roster()`：方舟干员 Half 网格长图。
- `render_ef_card()`：终末地角色卡片，支持 `show_all` 和 `simple` 背景。
- `render_gacha_history()`：明日方舟抽卡记录。
- `render_ef_gacha_history()`：终末地抽卡记录，返回分类分区、期次明细与内容高度约束的多页 PNG。
- `render_ef_war_echoes()`：战争回响赛季、荣勋、轮换与编队记录长图。
- `render_garrison_history()`：卫戍生涯、战绩与收藏列表分页，或单局完整阵容详情。
- `render_rogue_card()` / `render_rogue_info()`：肉鸽战绩总览 / 单局详情。
- `render_clue_board()`：线索看板。

模板位于 `resources/templates/`，过滤器位于 `filters.py`。Tailwind 输出 CSS 为 `nonebot_plugin_skland/resources/templates/index.css`。

`ArkCard.recruit_complete_time` 直接依赖 `filters.format_timestamp`，schema 不反向导入 `render.py`。`AP.ap_now` 在当前理智达到或超过自然上限时保留接口返回值，未满时按回满时间估算并限制在 `[current, max]`；角色卡显示实际值，进度条宽度最多 100%。背景选择位于 `utils/background.py`，本地来源返回 `Path`、远程来源返回 URL；渲染入口将本地路径转换为 `file://` URI，消息和 Argot 则保留真实路径，禁止跨边界复用同一种字符串表示。

账号角色卡的纹理、阴影和字体样式集中于 `tailwind.css` 的 `bound-roles-*` 类，终末地抽卡复用相同主题类而不更改角色卡样式。账号角色卡仍沿用 706px 视口、1.5 倍 PNG 和全局截图超时，不额外请求角色详情或远程图片。

终末地抽卡保留原有横幅、头像、进度条及统计元素，沿用角色卡的 `bound-roles-dossier` / `bound-roles-header` / `bound-roles-account` 纹理和灰阶面板，使用终末地字标与黄色强调色。局部几何样式仍在 `tailwind.css`，`resources/templates/ef_gacha.js` 只负责测量和分页，不计算业务统计。

卡池卡片只显示池名，不重复显示分类标题；UP 头像、总抽数、六星/歪卡使用紧凑信息行。重构系列累计、首次 UP 和免费十连使用短标签，下一奖励显示剩余次数；共享垫抽位于类别头，武器当期保底位于期次头。多金和免费批次沿用“十连 N 金”“免费10连”的用户术语，非十抽批次按真实抽数标注；无横幅资源时只保留细色条，不预留空横幅区域。

真实渲染 demo 必须装载当前卡池表和官方图标表两个进程内 singleton，并像命令一样在构造视图前补齐 UP/横幅，不能只调用分组函数。真实用户头像取自身份匹配的玩家接口；历史捕获与数据库已有记录应分别标明来源，不补造期次。验收使用实际渲染入口检查全部可见图片的解码/自然尺寸、CSS 图片、字体、页高与事件完整性，不以截图成功代替资源完整。

战争回响采用固定 422px 移动端布局。模板使用 `resources/images/endfield/war_echoes/` 中的随包静态素材，渲染时加载 API 返回的赛季 KV 和干员头像。

### 定时任务

`tasks.py` 注册三个 cron 任务：

```python
@scheduler.scheduled_job("cron", hour=0, minute=15, id="daily_arksign")
async def run_daily_arksign(): ...


@scheduler.scheduled_job("cron", hour=0, minute=20, id="daily_efsign")
async def run_daily_efsign(): ...


@scheduler.scheduled_job(
    "cron",
    hour=9,
    minute=0,
    id="daily_resource_update",
    max_instances=1,
    coalesce=True,
    misfire_grace_time=3600,
)
async def run_daily_resource_update(): ...
```

两项签到任务的结果分别写入插件缓存目录：

- `sign_result.json`
- `endfield_sign_result.json`

两项签到任务和签到命令共用 `services/sign.py` 的执行、缓存读写、owner/角色过滤及格式化；`schemas/sign.py` 提供 `SignCacheEntry`、`SignCache`、`SignResult`。结果文件名和有序列表 JSON 结构不变；事务提交与消息发送仍由调用方负责。缓存通过 `atomic_write()` 保存；读取时的解码失败、根对象或条目结构异常，以及签到成功结果不符合对应游戏的 `ArkSignResponse` / `EndfieldSignResponse`，统一转换为 `SignCacheFormatError` 并提示文件已损坏，`data` 为字典的旧格式保留原有提示。

每日数据任务受 `auto_update_resources` 控制，沿用 APScheduler 时区（默认 `Asia/Shanghai`），只执行数据更新和汇总日志，不发送 Bot 消息、不下载图片、不访问玩家接口。它与启动、手动数据更新共用互斥入口，停机后不承诺补跑错过的日程。

## 开发规范

### 代码风格

- 行长度：120。
- Python 目标版本：3.10。
- Ruff lint 规则在 `pyproject.toml` 的 `[tool.ruff.lint]`。
- Pyright 使用 `typeCheckingMode = "standard"`。
- 保持现有代码风格：异步函数、Pydantic 模型、NoneBot handler、短中文注释风格。

常用检查：

```bash
uvx isort .
uvx ruff format
uvx ruff check
```

### 测试

```bash
uv sync
uv run pytest --ignore=tests/test_skland_api.py
```

常规测试默认跳过 `tests/test_skland_api.py`，避免触发真实 API 请求、二维码登录或凭证缓存写入。需要验证森空岛真实接口时再单独运行，并保留 `-s` 以显示终端二维码输出：

```bash
uv run pytest -s tests/test_skland_api.py
```

测试说明：

- `tests/conftest.py` 使用 nonebug 初始化 NoneBot，并加载 `pyproject.toml` 中配置的插件。测试配置忽略项目 dotenv，localstore 使用 pytest 临时目录；htmlrender 本地授权仅覆盖测试临时目录，禁止通过测试配置绕过生产资源授权。
- 数据库测试使用内存 SQLite：`sqlite+aiosqlite://`。
- `make_user_session` fixture 将真实 `UserSession.user` 加入命令使用的同一个 SQLAlchemy session；解绑、缺少默认角色和签到选择失败的回归测试覆盖事务结束后用户 ORM 属性过期的行为，不能只用普通整数模拟 `user_id`。
- `tests/test_auth.py` 覆盖有界重试、缺少 token 时零刷新请求及刷新失败传播，并通过离线 HTTP 调用实际账号 API 和凭证接口，验证错误码分别触发 token 刷新、cred 更新或直接失败；`tests/test_player_data.py` 覆盖真实缓存中并发等待者分别刷新凭证与成功结果合并。
- `tests/test_download.py` 覆盖原有图片下载统计/计时隔离、跳过与覆盖规则、下载中断或取消时不留下残缺图片、存在失败时不推进版本及 `sync` 失败回复，以及数据客户端代理回退、凭证边界、错误响应校验、有限重试和并发限流；数据下载进度回归使用真实 Rich 输出，覆盖下载中进度可见、日志换行与重绘顺序、成功/失败/取消清理、非交互输出无框，以及保留文件日志和用户运行中修改的日志处理器。
- `tests/test_data_source.py` 使用离线 HTTP 传输与真实 loader 验证同版本不下载、固定提交直接下载、完整批次校验、失败零版本推进、写入回滚、冷启动缓存、损坏缓存警告、PRTS 回退及终末地等价数据不重写。
- `tests/test_ef_item_icons.py` 使用离线 HTTP 传输覆盖官网动态 CSS 发现、名称与游戏 ID 关联、历史名称变化、无玩家凭证的 Wiki 游客请求、官方域名和重定向限制、异常设备响应、完整构建后发布、冷/热 localstore 缓存、首次离线及写入失败；`tests/test_skland_api.py::TestPublicResources` 可单独验证无需扫码的真实公开目录。
- `tests/test_resource_updates.py` 覆盖手动/定时互斥、独立游戏和图片资源表失败、取消释放、关闭任务、09:00 时区边界、旧快捷指令缓存迁移为数据更新，以及用户回复的状态图标、卡池数量与角色/武器图片数量。
- `tests/test_ef_gacha_joint_pool.py` 覆盖终末地联合寻访分类与统计；`tests/test_ef_gacha_view.py` 覆盖免费/付费间隔隔离、多金事件完整性、分类切片不改变累计统计、UP 信息缺失时统计未知、免费 UP 不进入付费平均分母及仅有免费六星时平均值为空；`tests/test_ef_gacha_command.py` 覆盖默认同步、去重、先保存再渲染、显式缓存回退、接口解析失败的有/无缓存反馈、首/后续页失败零部分写入、鉴权错误优先级、选角身份、有序发送，以及角色/武器的 `kind` 过滤差异与原始分页边界。
- `tests/test_ef_gacha_rerun.py` 覆盖重构角色跨池小保底、免费抽隔离、同名跨期首次 UP 保证与奖励门槛、武器申领批次、多金、未知期次及残缺记录，以及同秒不同期的事件归属、五星隔离、武器展示分类独立切片与累计不变；`tests/test_ef_gacha_migration.py` 覆盖期次迁移保留旧记录、未知值与角色约束。抽卡命令回归同时覆盖稀疏游标、纯奖励页、失败零部分提交，以及旧重构武器重分类和期次回填后的重复同步。
- `tests/test_ark_gacha_command.py` 覆盖方舟抽卡正负切片的分页边界、角色资料/渲染/发送失败后记录已保存，以及小黑盒导入遇到未知干员时零写入并列出名称。
- `tests/test_operator_roster.py` 覆盖官方目录与 PRTS 元数据合并、自然筛选词、高级参数合并、快捷指令空格约束、持有状态/潜能组合、实装/获取/练度排序、技能/模组组合、实际模板中的已拥有/未拥有干员及三个模组完整展示，以及分页发送。
- `tests/test_ark_ap.py` 覆盖理智溢出保留、未满时的估算区间及回满时间已过的边界。
- `tests/test_image_cache.py` 覆盖配置开关、浏览器半身图响应落盘、本地复用、资源就绪与等待超时，以及失败响应不进入缓存。
- `tests/test_compact.py` 覆盖支持版本的模板渲染、资源授权和生命周期；包内素材与插件缓存可访问，旧数据资源目录和账号文件仍不可访问。真实 Chromium 回归验证 `memory`、`filehost` 策略下普通截图与自定义页面均不依赖浏览器读取本地文件，并保留文档内 fragment 引用；测试仅使用已安装的 Chromium，缺失时跳过且不自动安装。
- `tests/test_qrcode.py` 覆盖头像 URL 限制、图片下载校验、无头像降级、二维码原始像素保持、群聊发起者标记及扫码绑定流程。
- `tests/test_account_management.py` 覆盖多账号所有权、分游戏默认角色、角色同步、账号操作互斥、临时选角与角色卡序号一致、默认映射不变、按选定角色导入记录，以及缺少默认角色和跨用户临时选角时的隐私/事务边界。
- `tests/test_bound_roles.py` 覆盖 binding API 规范化、角色卡投影、序号、默认徽标、两游戏玩家 UID 选择、内部 ID 隐藏、昵称转义、四种展示模式及空态/不可用角色。
- `tests/test_multi_account_migration.py` 覆盖旧结构升级、数据保护检查、生成主键和不可表示数据的 downgrade 拒绝。
- `tests/test_bind.py` 覆盖 token/cred 确认式新增/更新、取消/超时零写入、确认期间状态变化，以及真实 UserSession 下选择性/全量解绑的双 waiter 和提交后反馈。
- `tests/test_sign.py` 覆盖多账号同名/同 UID 角色、角色所属凭证、签到缓存 list 结构、缓存截断或结构损坏时的状态反馈、序号选角和默认不变，以及签到/状态的 `--role`/`--all` 冲突、状态 owner/角色联合过滤、空结果和全体状态的 ORM 过期边界。
- `tests/test_role_selection.py` 覆盖全部 14 个选角入口的长短选项、`-r` / `-ra` 冲突隔离、旧 UID 语法拒绝、更新开关保留，以及存在默认角色时无效序号的真实 matcher 分发，确保没有回退默认和外部数据访问。
- `tests/test_war_echoes.py` 覆盖评级投影、荣勋累计、用户信息、当前/指定/相对赛季轮换选择、最高已通关难度和命令提交后渲染发送。
- `tests/test_garrison_api.py`、`tests/test_garrison_models.py` 覆盖卫戍无转换头的 JSON/模型边界、鉴权错误优先级与错误脱敏、空记录、战绩/收藏编号、跨版本投影、缺元数据保留阵容及生涯统计；素材回归验证包内固定图和称号路径、未知敌人 ID 仍可取图、空身份、代理与 ID 编码，以及跨活动头像隔离。区服回归验证渠道 ID 优先于旧区服名称及未知渠道回退。`tests/test_garrison_command.py` 覆盖跨账号临时选角、刷新持久化、默认角色不变、提交后渲染发送、失败不标完成、空收藏不回退，以及实际模板的默认首页、`-a` / `--all` 全部分页、收藏范围、跨首页单局编号、统计不截断、昵称转义及旧活动选项拒绝；发送回归覆盖 16/17/32/33 张图片的分批边界、完整顺序、全局页码，以及后续批次失败时不再继续发送且不标记完成。`tests/test_skland_api.py::TestRealAPI::test_garrison` 可单独读取当前真实赛季与战绩，不输出玩家或凭证。
- `tests/test_rogue_info.py` 覆盖战绩详情编号 0、负数、越界、列表为空及收藏不回退最近战绩，引用图片与 `-r` 两条路径一致。
- `tests/test_skland_api.py` 会调用真实接口；单独运行时使用 `uv run pytest -s tests/test_skland_api.py`，其中 `-s` 用于显示终端二维码输出；凭证优先级为：
  1. `tests/cred_cache.json`
  2. 环境变量 `SKLAND_TOKEN` 或 `SKLAND_CRED`
  3. 终端二维码扫码登录
- 不要提交真实凭证、二维码或临时凭证缓存。
- 如果开发中遇到新的接口需求，请在 `tests/test_skland_api.py` 新增接口测试，在开发者扫码运行后记录返回数据结构，将所需数据结构更新到 schemas 对应部分。

- 对非平凡逻辑（复杂条件、状态机、并发、错误恢复等）的改动：
  - 优先考虑添加或更新测试；
  - 在回答中说明推荐的测试用例、覆盖点以及如何运行这些测试。
- 不要声称你已经实际运行过测试或命令，只能说明预期结果和推理依据。

### 常用命令

```bash
# 安装/同步依赖
uv sync

# 运行常规测试（跳过真实 API 测试）
uv run pytest --ignore=tests/test_skland_api.py

# 如需验证森空岛真实接口，再单独运行；保留 -s 以显示扫码二维码
uv run pytest -s tests/test_skland_api.py

# 格式化与检查
uvx isort .
uvx ruff format
uvx ruff check

# 运行 Bot（需要 nb-cli 与适当适配器配置）
nb run

# 编译 Tailwind CSS（当前脚本带 -w，会进入 watch 模式）
# 该命令不会自动退出，不适合作为 CI/一次性验证命令。
# 适合在调试css时实时更新文件
pnpm run build

# 构建发布包
uv build
```

### 数据库迁移

本项目通过 nonebot-plugin-orm 使用 Alembic。修改 `model.py` 后应新增迁移：

```bash
nb orm revision -m "description" --branch-label "nonebot_plugin_skland"
nb orm upgrade
```

迁移脚本位于 `nonebot_plugin_skland/migrations/`。已有迁移包括初始表、抽卡记录表、`role_id`、模型类型修正、终末地抽卡支持、多账号身份重建，以及 `c8d95f314a62` 重构卡池期次；多账号 downgrade 在旧结构无法无损表达当前数据时必须拒绝执行。

## 添加新功能的一般流程

1. **确认命令入口**：如需要用户命令，先在 `matcher.py` 添加 Alconna 子命令/参数。
2. **定义数据模型**：在 `schemas/arknights/` 或 `schemas/endfield/` 中添加/调整 Pydantic 模型，并在对应 `__init__.py` 与顶层 `schemas/__init__.py` 导出。
3. **实现 API 调用**：在 `api/request.py` 或 `api/login.py` 添加接口封装，统一异常类型。
4. **实现 handler**：在 `commands/` 中按功能拆分逻辑，入口在 `__init__.py` 中用 `@skland.assign(...)` 注册。
5. **补充数据库操作**：需要持久化时修改 `model.py` / `db_handler.py`，并新增 Alembic 迁移。
6. **补充渲染**：需要图片输出时添加模板、过滤器和 `render.py` 函数。
7. **补充快捷指令与帮助**：同步更新 `hook.py`、`extras.py`、`README.md`。
8. **补充测试**：对纯统计/分组逻辑优先写单元测试；对真实 API 行为注意凭证与跳过条件。

## 添加新游戏支持建议

参考当前 `endfield/` 实现：

1. 在 `schemas/` 下创建游戏子包并导出模型。
2. 在 `api/request.py` 添加对应接口方法与签名/鉴权处理。
3. 若有卡池或静态数据，添加类似 `EfGachaPoolTableData` 的数据源管理类。
4. 在 `model.py` / `db_handler.py` 中支持新的 `app_code` 与查询逻辑。
5. 在 `commands/` 中创建游戏子包。
6. 在 `matcher.py` 和 `__init__.py` 注册命令。
7. 在 `resources/templates/` 和 `render.py` 添加渲染逻辑。
8. 在 `hook.py`、`extras.py`、`README.md` 添加快捷指令与文档。

## 渲染风格

- 整体保持当前项目的卡片式信息面板风格，使用固定宽度容器、分区卡片和紧凑网格展示数据。
- 页面应优先保证信息密度与可读性，标题、统计、列表、提示信息需要有清晰层级。
- 新增页面可以根据内容调整布局和视觉表现，但应先参考相近功能的现有模板。
- 字体、圆角、阴影、进度条、分割线等视觉元素可以直接复用现有模板和预设 CSS。
- 背景图上应使用遮罩或模糊层保证文字可读。
- 避免与现有模板明显割裂的视觉风格。

## 注意事项

1. **凭证安全**：`access_token`、`cred`、`cred_token`、`role_token` 都是敏感数据，不要写入日志、文档、测试输出或提交到仓库。
2. **真实 API 测试**：`test_skland_api.py` 可能触发二维码登录和真实接口请求；运行前确认环境适合。
3. **API 限流**：森空岛、GitHub、PRTS、终末地 Web API 均可能限流或不可用；批量请求应控制并发与错误处理。
4. **终末地数据缓存**：终末地卡池数据启动时会尝试下载，失败时可回退到本地缓存；不要假设网络一定可用。
5. **图片资源缓存**：渲染优先使用本地资源，不存在时再从网络获取；`sync --img` 可下载明日方舟图片资源。
6. **命令权限**：全体签到、全体状态、全体角色更新、资源同步等命令仅超管可用；绑定相关逻辑应避免泄露凭证。
7. **分页语义**：明日方舟 `gacha -b/-l` 作用于卡池序号；终末地 `efgacha -b/-l` 对每个类别分别切片。
8. **联合寻访**：终末地联合寻访使用独立类别 `joint_pools`，不要并入 `standard_pools`；相关统计和模板已有测试覆盖。
9. **异常类型**：接口层优先使用 `RequestException`、`LoginException`、`UnauthorizedException`，handler 再决定消息反馈或返回字符串。
10. **文档同步**：新增命令、配置、快捷指令、渲染模板或测试约定时，同步更新 `README.md`、`extras.py` 和本文件。
11. **保持代码干净**: 对于新增的代码，不要随意放到任意位置，按项目开发习惯或文件命名，专事专干，不要在专注渲染的代码文件里去做多余的事情，比如数据处理，这显然不止局限于此，以上仅是举出的一个反例。
    > 涉及到渲染部分时，前置数据处理特化的可以在接收到数据时，在 `schemas` 部分处理好，通用的数据格式化等处理，可以在 `filters` 内处理，尽量避免在 `render` 中处理非渲染部分的业务。
12. **pydantic兼容**: 在涉及`pydantic v2` 和 `v1` 的版本差异的内容上，优先采用 `nonebot.compat` 中的对应兼容。
13. **用户体验** 注意项目用意，服务于用户交互体验，不要设计繁琐难记的交互指令，同时，不要有反人类的交互逻辑和代码执行设计。
14. **用户文档只讲功能与用法**：`README.md` 只介绍已实现的功能、命令与配置用法、使用示例，以及影响使用的必要提醒；不要描述发送分批阈值、批次顺序、内部数据流等细枝末节的实现行为。`extras.py`（图片帮助）同样遵循这一边界。用法没变的内部重构，不要添加用户说明；实现细节、技术约束和开发约定只记录在本文件。接口数据的时间范围、留存上限和完整性必须有已确认的依据，不得由字段名、本地命名或自行添加的界面标签推断。

## 语言与编码风格

- 解释、讨论、分析、总结：使用 **简体中文**。
- 变量名、函数名、类型名等代码标识符使用 **English**；中文用户文案、模板文字及对应测试期望直接写汉字，不使用 Unicode 转义或数字 HTML 实体代替中文。注释遵循所在文件的风格，优先保证可读性。
- 提交信息请按照当前 repo 的历史提交习惯，采用 gitmoji 规范
- Markdown 文档正文使用中文；代码块内的标识符使用 English，中文文案和命令示例可直接使用汉字。
- 命名与格式：
  - Python：遵循 PEP 8；
  - 其他语言遵循对应社区主流风格。
- 在给出较大代码片段时，默认该代码已经过对应语言的自动格式化工具处理（如 `ruff format`、`isort` 等）。
- 注释：
  - 仅在行为或意图不明显时添加注释；
  - 注释优先解释 “为什么这样做”，而不是复述代码 “做了什么”。

### 包管理

- 使用各语言的主流包管理工具（Rust 的 Cargo、Go 的 go modules、JS 的 bun、Python 的 uv 等）。
- 在添加新依赖时，优先选择社区认可度高、维护活跃的库。禁止直接修改例如 `package.json`、`Cargo.toml`、`pyproject.toml` 等以修改依赖，而是使用对应的命令行工具（如 `cargo add`、`go get`、`uv`、`bun` 等）。
- 同样，也需要使用例如 `uv init`、`cargo init` 等命令行工具来初始化项目，而不是手动创建文件。

## 相关资源

- [NoneBot2 文档](https://nonebot.dev/)
- [Alconna 文档](https://arclet.top/tutorial/alconna/v1.html)
- [森空岛](https://skland.com/)
- [ArknightsGameResource](https://github.com/yuanyan3060/ArknightsGameResource)
- [EndfieldGachaPoolTable](https://github.com/FrostN0v0/EndfieldGachaPoolTable)

## 编程哲学与质量准则

- 代码首先是写给人类阅读和维护的，机器执行只是副产品。
- 优先级：**可读性与可维护性 > 正确性（含边界条件与错误处理） > 性能 > 代码长度**。
- 严格遵循各语言社区的惯用写法与最佳实践（Rust、Go、Python 等）。
- 严格遵循 Nonebot2 社区中的最佳实践。
  - **数据库 orm** 优先使用 `nonebot-plugin-orm`
  - **用户信息相关** 优先使用 `nonebot-plugin-uninfo` 和 `nonebot-plugin-user`
  - **命令解析与跨平台支持** 优先使用 `nonebot-plugin-alconna`
  - **本地数据存储** 优先使用 `nonebot-plugin-localstore`
  - 不限于上述示例，你应当在不同的设计需求时，优先去检索并使用对应的社区最佳实践。
  - 若当前项目未引入对应插件，新增依赖前需确认必要性。
  - 引入上述插件，请遵循 `Nonebot2` 规范，先 `require` 后 `import`
- 主动留意并指出以下“坏味道”：
  - 重复逻辑 / 复制粘贴代码；
  - 模块间耦合过紧或循环依赖；
  - 改动一处导致大量无关部分破坏的脆弱设计；
  - 意图不清晰、抽象混乱、命名含糊；
  - 没有实际收益的过度设计与不必要复杂度。
  - 过度怠于浅显的局部更改（如能使用 `use` 而不使用，而是撰写 `std::sync::..`）。
- 当识别到坏味道时：
  - 用简洁自然语言说明问题；
  - 给出 1–2 个可行的重构方向，并简要说明优缺点与影响范围。
- Avoid unnecessary secondary labels, descriptions, and other textual descriptions. Let the layout do the explaining—a good UI is self-explanatory.

---
