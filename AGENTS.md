# AGENTS.md

本文档为 AI 编程代理（如 Codex、Claude Code 等）提供本仓库的项目上下文与开发指南。内容应以当前源码为准；修改实现后请同步更新本文档。

## 项目概述

**nonebot-plugin-skland** 是一个基于 NoneBot2 的 Python 插件，用于通过森空岛（Skland）及鹰角相关 Web API 查询游戏数据。

当前支持：

- **明日方舟（Arknights）**：角色信息卡片、每日签到、肉鸽战绩与单局详情、抽卡记录查询、从小黑盒导入抽卡记录、方舟干员查询。
- **明日方舟：终末地（Endfield）**：角色信息卡片、每日签到、抽卡记录查询与更新；抽卡统计支持角色池、武器池、新手池、常驻池、限定池、联合寻访池。

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
- **包管理**: uv；构建后端为 pdm-backend

## 目录结构

```text
nonebot_plugin_skland/
├── __init__.py          # 插件元数据、依赖 require、命令处理器注册
├── matcher.py           # Alconna 命令树、别名 sk、Argot/ReplyRecord 扩展
├── hook.py              # 启动/关闭钩子：加载数据、注册/持久化快捷指令、可选资源检查
├── tasks.py             # APScheduler：每日签到与 09:00 数据资源更新
├── config.py            # Pydantic 配置、资源/缓存/数据目录常量
├── extras.py            # NoneBot 插件商店/帮助菜单 extra 数据
├── model.py             # nonebot-plugin-orm 模型：SkUser、Character、CharacterDefault、GachaRecord
├── account.py           # 多账号角色快照、默认角色投影、角色同步与账号操作互斥
├── db_handler.py        # 账号、角色、默认角色与抽卡记录查询/写入契约
├── data_source.py       # 游戏数据下载、干员目录构建与本地元数据缓存
├── player_data.py       # 玩家实时数据账号级短期缓存：ArkCard TTL/LRU/single-flight
├── image_cache.py       # 方舟半身图浏览器响应缓存与显式资源就绪等待
├── download.py          # 图片下载与数据专用 GitHub 客户端：提交定位、连接池及代理回退
├── render.py            # HTML 模板渲染为图片的函数
├── filters.py           # Jinja2 过滤器与可复用图片资源 URL 函数
├── exception.py         # Shared API and account-operation errors
├── services/
│   ├── __init__.py      # Package boundary without implicit exports
│   ├── auth.py          # Credential refresh policy and detached credential state
│   ├── binding.py       # Binding preparation and atomic confirmed account mutations
│   ├── gacha.py         # History fetching, grouping, and Heybox conversion
│   ├── resources.py     # 启动、手动、定时数据更新互斥与汇总反馈
│   └── sign.py          # Signing, ordered cache persistence, filtering, and formatting
├── utils/
│   ├── __init__.py      # Package boundary without implicit exports
│   ├── background.py    # Configured background selection
│   ├── message.py       # Command reactions and API error feedback
│   └── qrcode.py        # Safe avatar fetching and pixel-preserving QR cards
├── api/
│   ├── __init__.py      # API 模块导出
│   ├── request.py       # SklandAPI：森空岛/抽卡/终末地接口与签名逻辑
│   ├── login.py         # SklandLoginAPI：token、cred、扫码登录相关接口
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
│   ├── sync.py          # 资源与数据同步命令
│   └── endfield/
│       ├── __init__.py  # 终末地 handler 导出
│       ├── card.py      # 终末地角色卡片
│       ├── sign.py      # 终末地签到与签到状态
│       └── gacha.py     # Endfield gacha history update and paginated rendering
├── schemas/
│   ├── __init__.py      # 对外集中导出 Pydantic 模型
│   ├── binding.py       # 森空岛 wire model、确认快照与绑定角色卡 DTO
│   ├── cred.py          # CRED 凭证模型
│   ├── sign.py          # Shared SignResult and sign-cache contracts
│   ├── arknights/
│   │   ├── card.py      # ArkCard 角色卡片结构
│   │   ├── sign.py      # Arknights sign API response
│   │   ├── game_data.py # 抽卡详情、官方干员目录与 PRTS 元数据快照结构
│   │   ├── operator_query.py # Natural filters, aliases, and query validation
│   │   ├── operators.py # Operator card/module projections and roster ordering
│   │   ├── gacha/       # 明日方舟抽卡基础、卡池、统计模型
│   │   ├── rogue/       # 肉鸽基础数据、生涯统计、历史记录模型
│   │   └── models/      # 角色卡片的状态、干员、基建、招募、活动、皮肤等详细模型
│   └── endfield/
│       ├── card.py      # EndfieldCard 与终末地角色卡片结构
│       ├── sign.py      # EndfieldSignResponse
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
        ├── endfield_card.html.jinja2
        ├── gacha.html.jinja2
        ├── gacha_macros.html.jinja2
        ├── ef_gacha.html.jinja2
        ├── ef_gacha_macros.html.jinja2
        ├── ef_gacha.js       # Fixed category columns and ordered event continuations
        ├── rogue.html.jinja2
        ├── rogue_info.html.jinja2
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

业务用例集中在 `services/`，图片和消息工具集中在 `utils/`，不将拆分结果平铺到包根目录。两者的 `__init__.py` 不聚合导出；调用方直接导入对应子模块，不保留旧路径兼容转发。

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
skland rginfo <id> [-r|--role <index>] [-f]
skland gacha [target] [-r|--role <index>] [-b <begin>] [-l <limit>]
skland import <url> [-r|--role <index>]
skland box [target] [filters ...] [-r|--role <index>] [-o <owned|unowned|all>] [-ra <rarity>] [-p <profession>] [-b <branch>] [--position <position>] [--gender <gender>] [-f <faction>] [--race <race>] [--potential <potential>] [-s <release|acquired|training>] [-n <name>]
skland efcard [target] [-r|--role <index>] [-a] [-s]
skland efgacha [target] [-r|--role <index>] [-b <begin>] [-l <limit>]
```

内置快捷指令在 `hook.py` 启动时注册，并通过 `nonebot_plugin_alconna.command_manager` 持久化到插件缓存目录的 `shortcut.db`。当前包括：森空岛绑定、扫码绑定、森空岛解绑、森空岛角色、切换方舟角色、切换终末地角色、明日方舟签到、签到详情、全体签到、全体签到详情、各肉鸽主题、角色更新、全体角色更新、资源更新、战绩详情、收藏战绩详情、方舟抽卡记录、导入抽卡记录、方舟干员、终末地签到、终末地签到详情、终末地全体签到、终末地全体签到详情、`ef|zmd`、终末地抽卡记录。启动加载缓存后会清理旧的“终末地抽卡更新”入口。

`森空岛角色` 精确匹配 `skland char`；`切换方舟角色 <index>` / `切换终末地角色 <index>` 分别映射到 `skland char set ark <index>` / `skland char set ef <index>`，使用 `fuzzy=True` 接收序号、`compact=False` 要求空格分隔，并沿用 Bot 的命令前缀。内置快捷指令在加载缓存后注册。

个人签到快捷指令保留裸命令签到全部个人角色的行为；追加选项时由独立的带空白前缀规则转发到 `sign`，支持 `-r` / `--role`，不会隐式叠加 `--all`。签到详情快捷指令也允许追加选角参数。其他按角色查询的中文快捷指令继续透传参数。

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

账号删除通过数据库/ORM 级联删除其角色、默认映射和抽卡记录。新增或修改模型后需要添加迁移脚本。

### API 与签名

`api/request.py` 中 `SklandAPI.get_sign_header()` 负责生成森空岛签名请求头。

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
- `endfield_sign()`：终末地签到。
- `get_ef_gacha_history()`：终末地角色池/武器池抽卡记录。
- `get_ef_gacha_content()`：终末地卡池 UP 内容。

`api/login.py` 的 `SklandLoginAPI` 负责 token/cred 互换、cred_token 刷新、二维码扫码登录、role token 获取等。

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
- `account.sync_account()` 使用普通凭证快照执行 API 请求，再重新读取账号并事务性同步角色/默认映射；不构造未持久化的 `SkUser` 充当临时凭证对象。
- `skland char` 返回全部账号和角色；`skland char set <game> <index>` 按游戏独立序号切换插件默认角色，所有业务功能使用该角色所属账号的凭证。
- 角色卡片、两游戏抽卡查询/更新、抽卡导入、干员查询、肉鸽及详情、两游戏个人签到及状态共 12 个入口统一支持 `-r` / `--role`。`matcher._role_option()` 为每个作用域构建独立选项，命令分发传入 `role_index`；各 handler 共用 `commands/selection.py` 的 `check_user_character(app_code=...)`，使用角色所属账号、不写 `CharacterDefault`、不要求已有默认角色，也不能临时选择他人的角色。`get_character_by_index()` 与 `char set` 共用 `get_user_characters()` 排序，无效序号不回退默认。
- `skland box -r` 统一用于角色序号，原星级短选项改为 `-ra`；`--rarity`、`rarity` 和自然筛选词继续保留。所有旧示例和调用必须同步迁移，不能根据值猜测 `-r` 是星级还是角色。
- 签到状态不带选角参数时保留本人全部角色结果；显式选角时按 owner 和角色主键共同过滤缓存，防止跨账号、跨用户混入。`--all` 为超管全体状态，与选角互斥；全体签到提交后展示状态时不读取已过期的 `UserSession.user`。
- 肉鸽详情不带选角参数时使用引用图片的缓存数据；显式选角时获取所选角色的新数据，引用图片只提供主题，无引用时使用角色当前主题。肉鸽 API 读取后在渲染前提交凭证刷新；线索、背景等暗语继续沿用原卡片携带的数据。
- 个人签到的 `-u` / `--uid` / `uid` 选角入口已移除；`--role` 与 `--all` 同时出现时拒绝执行。绑定、同步和抽卡中表示更新的 `-u` 维持原义。主卡片 handler 使用选项感知的分发，根 `--role` 与不支持的子命令组合会明确拒绝，避免误触发双 handler。
- 账号角色卡使用本地灰阶纹理、游戏字标与档案式布局；身份资料仅展示昵称、玩家 UID 和区服名称，保留账号/角色选择序号与默认/操作状态，不展示账号尾号、终末地绑定 UID、服务器内部编号或等级。
- 角色选择编号仅显示数字，不在数字下方重复标注“序号”，也不在卡片右下角显示分游戏编号说明。
- `BoundRoleCardItem.player_uid` 对方舟返回 `binding_uid`，对终末地返回 `game_role_id`；内部字段继续保留用于身份识别与确认校验。模板显式开启 Jinja autoescape，避免依赖 htmlrender 默认不转义的环境。
- `BoundRoleCardItem.server_label` 按方舟渠道 ID 将 `1` / `2` 显示为“官服” / “bilibili服”，覆盖旧迁移将编号存入 `server_name` 的记录；终末地接口区服名 `China` 仍显示为“国服”。未知渠道沿用原区服名，不修改数据库、API 请求和角色身份匹配使用的原始名称或服务器 ID。
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
  - `load(force=False, refresh_metadata=False, *, client=None)` 可借用共享客户端，返回是否实际持久化了变更。必需更新失败时先恢复可用冷缓存再抛出 `RequestException`，不能把缓存回退报告为“已是最新”。旧 `get_version`、`download_game_data`、`_update_version_file` 与 `origin_version` 路径已移除。
- `EfGachaPoolTableData`
  - 从 `FrostN0v0/EndfieldGachaPoolTable` 拉取 `GachaPoolTable.json`。
  - 通过相同客户端定位上游提交，直接获取该提交的卡池表；解析验证成功后才替换文件。同语义内容（包括强制检查）不重写缓存；失败保留可用旧数据并抛错。
  - 提供 `get_pool(pool_id)` 为终末地抽卡渲染补充 UP 信息。

`services/resources.py` 的 `update_data_resources()` 为启动、手动及每日任务提供共用入口，一轮借用同一个 `GitHubDataClient`，分别处理两游戏失败并返回汇总。进程内已有更新时抛出 `ResourceUpdateInProgress`；命令提示稍后重试，定时任务跳过，不并发写同一组文件。`hook.py` 启动使用此入口加载两游戏数据，并在加载快捷指令缓存后将“资源更新”替换为 `skland sync --data`，使用 `compact=False` 要求参数前有空格。

数据更新结果保留独立、带 `✅` 的 INFO 日志：干员筛选元数据包含条数，明日方舟游戏数据包含版本，终末地卡池数据包含卡池数；不能用英文 DEBUG 替代这些可见结果，也不合并成一条“启动数据资源更新”汇总。

用户侧数据更新回复保留状态图标：更新成功使用 `✅`，已是最新使用 `📦`，更新失败使用 `❌`。终末地卡池数据无论更新成功还是已是最新，都返回当前卡池数量；仍在命令结束后合并发送一条结果消息。

`GitHubDataClient` 默认经配置代理获取 GitHub 数据；原站回退、瞬时故障的有限重试和连接池限流属于单轮更新。失效代理不会让后续文件重复等待相同长超时，GitHub Token 仅传给直连官方 API。PRTS 地址不加 GitHub 代理。此客户端不使用 jsDelivr，也不需要额外镜像仓库或 CI。

数据下载并发上限固定为内部常量 8，不提供用户配置。数据文件流式读取时复用现有 `DownloadProgress` 面板，显示文件名、下载量、速度及响应提供总长度时的百分比；下载开始和完成沿用现有日志风格。首次没有数据缓存是正常初始化，不记录警告；已有缓存无法解析或缺损时仍给出警告，真实下载失败继续报告失败并保留旧数据。

下载框使用临时显示，仅在有实际下载任务时启动，最后一项结束或异常退出时立即清除并恢复光标。框活动期间默认 NoneBot 控制台日志经同一 Rich Console 输出，保留格式、等级和换行；结束后恢复普通控制台输出，不修改其他自定义或文件日志处理器。非交互终端与重定向输出仅输出普通日志，不产生下载边框和光标控制序列。默认控制台处理器被用户替换或已有其他 Live 窗口时，不接管自定义处理器，也不维持第二个下载框。

若 `check_res_update=True`，启动仍调用 `download.download_img_resource()` 检查图片。手动 `skland sync` / `--img` 保持原有图片行为；图片 `download_all()` 的计数、版本/覆盖规则和并发上限不在本次数据更新改动范围内。

### 抽卡记录

明日方舟：

- `commands/gacha.py` 编排查询与持久化，`services/gacha.py` 负责分页读取、分组及小黑盒导入转换。
- `services.gacha.group_gacha_records()` 按卡池与时间戳分组，并补充 UP 干员、开放时间、卡池规则类型。
- `render.render_gacha_history()` 使用 `gacha.html.jinja2` 渲染。

### 方舟干员

- 唯一用户快捷入口为 `方舟干员`，映射到 `skland box`；`fuzzy=True` 允许追加参数，`compact=False` 强制筛选词之间使用空格。启动加载旧快捷指令缓存后会删除历史的 `干员盒` 和 `图鉴` 入口。
- `matcher.py` 使用 `MultiVar(str, "*")` 接收任意数量的自然筛选词；QQ 号或 @ 目标位于筛选词之前，裸数字不作为星级或潜能。
- `commands/box.py` 将自然筛选词和高级 Options 一次性交给 `OperatorRosterQuery.from_input()`，不维护两套筛选路径；结果按 `roster_render_max` 分块并发渲染，QQClient 使用合并转发，其他平台逐图发送。
- `schemas/arknights/operator_query.py` 统一解析持有状态、星级、职业、分支、部署位置、性别、势力、种族、潜能、名称和排序。相同集合维度合并为 OR，不同维度为 AND；冲突的持有状态、排序和名称直接报错，无法识别的连写词提示使用空格。
- `schemas/arknights/operators.py` 的 `OperatorCard`、`OperatorModule`、`OperatorRoster` 负责玩家数据合并和排序，单向依赖查询模型；API 中存在但本地目录尚未收录的持有干员通过 fallback 条目保留。
- `Character.potential_level` 将 API 的 `potentialRank` 0-5 转为用户可见的潜能 1-6。练度排序依次比较精英阶段、等级、专精总和、专三数量、已解锁模组最高/总等级、技能等级和信赖，不包含潜能。
- 实装排序使用官方目录 `sort_id`，获取排序使用 `gainTime`；`all` 使用获取或练度排序时先排列已拥有干员，再将未拥有干员按实装顺序放在末尾。`unowned` 不允许潜能、获取或练度条件。
- `schemas/arknights/game_data.py` 从官方数据构造稳定目录，并以 PRTS 快照补充职业分支中文名、性别和种族；阿米娅各职业形态保持独立身份。
- `filters.py` 统一提供立绘、技能、潜能、精英阶段、职业、稀有度、模组及 Half 卡片装饰资源 URL。
- `image_cache.py` 仅在 `ark_portrait_cache_enabled=True` 时登记 `char/portrait` 与 `char_skin/portrait` 拼链资源。首次 HTML 仍保留远程 URL，Chromium 正常并发加载；成功的 `requestfinished` 响应经校验后原子写入 `CACHE_DIR/portrait`，后续渲染由 URL helper 返回本地 URI。不会额外发起图片请求或重新生成 HTML，接口直接返回的图片 URL 不参与缓存。
- `render.render_operator_roster()` 使用 `load`、`document.fonts.ready` 与图片 `decode()` 显式判断资源就绪，不再等待每页 `networkidle`；远程背景通过隐藏图片节点纳入等待。仍使用每页独立 BrowserContext、固定 706px Playwright 视口、1.5 设备缩放和可配置截图超时，默认输出 JPEG 90，可配置切回 PNG。
- `operator_roster.html.jinja2` 维护 706px、4 列固定网格；筛选标签支持自动换行，样式编译到 `resources/templates/index.css`。

终末地：

- `services.gacha.sync_ef_gacha_records()` 获取 `STANDARD`、`SPECIAL`、`BEGINNER`、`JOINT` 和 `WEAPON` 五类记录，全部获取成功后按现有角色身份去重（包括同批响应内重复项）并提交，再返回脱离 ORM 的统计数据。获取失败不保存不完整的新记录。
- `skland efgacha` 和“终末地抽卡记录”统一完成获取、保存和展示，移除 `-u` 及旧更新快捷指令。缺少 token 或接口失败时，仅在已有本地记录的情况下回退，并明确标注本次未更新；错误反馈不包含可能携带凭证的原始请求 URL。
- `commands/endfield/gacha.py` 在事务结束前保存普通角色/账号身份，渲染不再持有 ORM 角色。头像请求失败不阻断已保存历史的展示，刷新后的凭证在渲染前单独提交；全部图片发送成功后才标记完成。
- `services.gacha.get_all_ef_gacha_records(server_id, ...)` 沿用并发分页，不依赖 ORM `Character`。
- `services.gacha.group_ef_gacha_records()` 将记录分为 `beginner_pools`、`standard_pools`、`special_pools`、`joint_pools`、`weapon_pools`。
- `EfGroupedGachaRecord` 负责各类统计：总抽数、六星平均抽数、保底、UP/歪卡、武库配额、可见卡池切片。
- `EfGachaView.from_record()` 保留完整累计统计，按各类别 `-b` / `-l` 选择池集合后，预先计算带五星汇总的付费六星事件与免费批次；免费抽不改变付费计数，多金分组和出货间隔不因分页重算。渲染只操作这些完整事件。
- `render.render_ef_gacha_history(EfGachaView)` 返回有序 PNG 列表，固定 800px 三列：左列限定池，中列武器池，右列依次为新手、常驻、联合寻访。同类按最近抽卡时间倒序排列；每列只处理队首卡池，达到高度或该类别的每页池数上限时在下一页原列继续，不跨列补位，也不跳过较大的池先放后面的短池。短池保持完整，单池本身超长时才按完整事件续段；单页逻辑高度上限 1600px，累计统计仅首页展示。

### 渲染系统

渲染入口在 `render.py`。一般模板沿用 `cached_template_to_pic()`；终末地抽卡使用 htmlrender 的模板生成和独立 Playwright 页面，复用 `image_cache.wait_for_page_resources()` 等待字体/图片，完成 DOM 高度排版后逐页截图，所有阶段沿用全局 `render_timeout`。

主要函数：

- `render_ark_card()`：明日方舟角色卡片。
- `render_bound_roles_card()`：多账号角色总览、绑定确认和解绑选择/确认卡片。
- `render_operator_roster()`：方舟干员 Half 网格长图。
- `render_ef_card()`：终末地角色卡片，支持 `show_all` 和 `simple` 背景。
- `render_gacha_history()`：明日方舟抽卡记录。
- `render_ef_gacha_history()`：终末地抽卡记录，返回固定三列、内容高度约束的多页 PNG。
- `render_rogue_card()` / `render_rogue_info()`：肉鸽战绩总览 / 单局详情。
- `render_clue_board()`：线索看板。

模板位于 `resources/templates/`，过滤器位于 `filters.py`。Tailwind 输出 CSS 为 `nonebot_plugin_skland/resources/templates/index.css`。

`ArkCard.recruit_complete_time` 直接依赖 `filters.format_timestamp`，schema 不反向导入 `render.py`。背景选择位于 `utils/background.py`，不混入渲染入口。

账号角色卡的纹理、阴影和字体样式集中于 `tailwind.css` 的 `bound-roles-*` 类，终末地抽卡复用相同主题类而不更改角色卡样式。账号角色卡仍沿用 706px 视口、1.5 倍 PNG 和全局截图超时，不额外请求角色详情或远程图片。

终末地抽卡保留原有横幅、头像、进度条及统计元素，沿用角色卡的 `bound-roles-dossier` / `bound-roles-header` / `bound-roles-account` 纹理和灰阶面板，使用终末地字标与黄色强调色。局部几何样式仍在 `tailwind.css`，`resources/templates/ef_gacha.js` 只负责测量和分页，不计算业务统计。

卡池卡片只显示池名，不重复显示分类标题；UP 头像、总抽数、六星/歪卡和垫抽合并为紧凑信息行，空间不足时允许换行。多金和免费批次沿用“十连 N 金”“免费10连”的用户术语，不显示 FREE 占位图或重复免费徽标；无横幅资源时只保留细色条，不预留空横幅区域。

### 定时任务

`tasks.py` 注册三个 cron 任务：

```python
@scheduler.scheduled_job("cron", hour=0, minute=15, id="daily_arksign")
async def run_daily_arksign(): ...


@scheduler.scheduled_job("cron", hour=0, minute=20, id="daily_efsign")
async def run_daily_efsign(): ...


@scheduler.scheduled_job(
    "cron", hour=9, minute=0, id="daily_resource_update",
    max_instances=1, coalesce=True, misfire_grace_time=3600,
)
async def run_daily_resource_update(): ...
```

两项签到任务的结果分别写入插件缓存目录：

- `sign_result.json`
- `endfield_sign_result.json`

两项签到任务和签到命令共用 `services/sign.py` 的执行、缓存读写、owner/角色过滤及格式化；`schemas/sign.py` 提供 `SignCacheEntry`、`SignCache`、`SignResult`。结果文件名和有序列表 JSON 结构不变；事务提交与消息发送仍由调用方负责。

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

- `tests/conftest.py` 使用 nonebug 初始化 NoneBot，并加载 `pyproject.toml` 中配置的插件。
- 数据库测试使用内存 SQLite：`sqlite+aiosqlite://`。
- `make_user_session` fixture 将真实 `UserSession.user` 加入命令使用的同一个 SQLAlchemy session；解绑、缺少默认角色和签到选择失败的回归测试覆盖事务结束后用户 ORM 属性过期的行为，不能只用普通整数模拟 `user_id`。
- `tests/test_auth.py` 覆盖有界重试、缺少 token 时零刷新请求及刷新失败传播；`tests/test_player_data.py` 覆盖真实缓存中并发等待者分别刷新凭证与成功结果合并。
- `tests/test_download.py` 覆盖原有图片下载统计/计时隔离、跳过与覆盖规则，以及数据客户端代理回退、凭证边界、错误响应校验、有限重试和并发限流；数据下载进度回归使用真实 Rich 输出，覆盖下载中进度可见、日志换行与重绘顺序、成功/失败/取消清理、非交互输出无框，以及保留文件日志和用户运行中修改的日志处理器。
- `tests/test_data_source.py` 使用离线 HTTP 传输与真实 loader 验证同版本不下载、固定提交直接下载、完整批次校验、失败零版本推进、写入回滚、冷启动缓存可用、首次下载不误报警告、损坏缓存保留警告、PRTS 回退及终末地等价数据不重写。
- `tests/test_resource_updates.py` 覆盖手动/定时互斥、独立游戏失败、取消释放、关闭任务、09:00 时区边界、旧快捷指令缓存迁移为数据更新，以及用户回复的状态图标和终末地更新/未变化时的卡池数量。
- `tests/test_ef_gacha_joint_pool.py` 覆盖终末地联合寻访分类与统计；`tests/test_ef_gacha_view.py` 覆盖免费/付费间隔隔离、多金事件完整性及分类切片不改变累计统计；`tests/test_ef_gacha_command.py` 覆盖默认同步、去重、先保存再渲染、显式缓存回退、失败零部分写入、选角身份及有序发送。
- `tests/test_operator_roster.py` 覆盖官方目录与 PRTS 元数据合并、自然筛选词、高级参数合并、快捷指令空格约束、持有状态/潜能组合、实装/获取/练度排序、技能/模组组合、JPEG/PNG 参数、分页发送与渲染参数。
- `tests/test_image_cache.py` 覆盖配置开关、单次模板生成、浏览器半身图响应落盘、本地复用、显式字体/图片就绪、等待超时、未知 URL 跳过与失败响应忽略。
- `tests/test_qrcode.py` 覆盖头像 URL 限制、图片下载校验、无头像降级、二维码原始像素保持、群聊发起者标记及扫码绑定流程。
- `tests/test_account_management.py` 覆盖多账号所有权、分游戏默认角色、角色同步、账号操作互斥、临时选角与角色卡序号一致、默认映射不变、按选定角色导入记录，以及缺少默认角色和跨用户临时选角时的隐私/事务边界。
- `tests/test_bound_roles.py` 覆盖 binding API 规范化、角色卡投影、序号、默认徽标、两游戏玩家 UID 选择、内部 ID 隐藏、昵称转义、四种展示模式及空态/不可用角色。
- `tests/test_multi_account_migration.py` 覆盖旧结构升级、数据保护检查、生成主键和不可表示数据的 downgrade 拒绝。
- `tests/test_bind.py` 覆盖 token/cred 确认式新增/更新、取消/超时零写入、确认期间状态变化，以及真实 UserSession 下选择性/全量解绑的双 waiter 和提交后反馈。
- `tests/test_sign.py` 覆盖多账号同名/同 UID 角色、角色所属凭证、签到缓存 list 结构、序号选角和默认不变，以及签到/状态的 `--role`/`--all` 冲突、状态 owner/角色联合过滤、空结果和全体状态的 ORM 过期边界。
- `tests/test_role_selection.py` 覆盖全部 12 个选角入口的长短选项、`-r` / `-ra` 冲突隔离、旧 UID 语法拒绝、更新开关保留，以及存在默认角色时无效序号的真实 matcher 分发，确保没有回退默认和外部数据访问。
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

迁移脚本位于 `nonebot_plugin_skland/migrations/`。已有迁移包括初始表、抽卡记录表、`role_id`、模型类型修正、终末地抽卡支持和多账号身份重建；多账号 downgrade 在旧结构无法无损表达当前数据时必须拒绝执行。

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

---
