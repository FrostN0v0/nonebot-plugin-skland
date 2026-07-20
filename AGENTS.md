# AGENTS.md

本文档为 AI 编程代理（如 Codex、Claude Code 等）提供本仓库的项目上下文与开发指南。内容应以当前源码为准；修改实现后请同步更新本文档。

## 项目概述

**nonebot-plugin-skland** 是一个基于 NoneBot2 的 Python 插件，用于通过森空岛（Skland）及鹰角相关 Web API 查询游戏数据。

当前支持：

- **明日方舟（Arknights）**：角色信息卡片、每日签到、肉鸽战绩与单局详情、抽卡记录查询、从小黑盒导入抽卡记录、剿灭奖励提醒、干员盒与图鉴查询。
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
├── tasks.py             # APScheduler 定时任务：每日明日方舟/终末地签到
├── config.py            # Pydantic 配置、资源/缓存/数据目录常量
├── extras.py            # NoneBot 插件商店/帮助菜单 extra 数据
├── model.py             # nonebot-plugin-orm 模型：SkUser、Character、GachaRecord、CampaignReminder
├── db_handler.py        # 数据库查询、更新、删除与抽卡记录存取函数
├── data_source.py       # 明日方舟/终末地卡池数据下载、加载与缓存
├── download.py          # GitHub 资源下载器与版本检查
├── render.py            # HTML 模板渲染为图片的函数
├── roster.py            # 干员盒/图鉴：catalog、筛选、卡片组装
├── filters.py           # Jinja2 模板过滤器
├── utils.py             # Token 刷新装饰器、绑定同步、背景图、抽卡分组、资源下载等工具
├── exception.py         # LoginException / RequestException / UnauthorizedException
├── api/
│   ├── __init__.py      # API 模块导出
│   ├── request.py       # SklandAPI：森空岛/抽卡/终末地接口与签名逻辑
│   ├── login.py         # SklandLoginAPI：token、cred、扫码登录相关接口
│   └── dId.py           # dId 获取逻辑（部分接口签名需要）
├── commands/
│   ├── __init__.py      # 命令 handler 导出
│   ├── arksign.py       # 明日方舟签到与签到状态查询
│   ├── campaign.py      # 剿灭奖励提醒开关与状态
│   ├── bind.py          # token/cred 绑定、二维码绑定、解绑
│   ├── box.py           # 干员盒 / 图鉴查询
│   ├── card.py          # 明日方舟角色卡片查询
│   ├── char.py          # 同步森空岛绑定角色
│   ├── gacha.py         # 明日方舟抽卡记录查询、分页、导入小黑盒记录
│   ├── rogue.py         # 肉鸽战绩查询与单局详情
│   ├── sync.py          # 资源与数据同步命令
│   └── endfield/
│       ├── __init__.py  # 终末地 handler 导出
│       ├── card.py      # 终末地角色卡片
│       ├── sign.py      # 终末地签到与签到状态
│       ├── gacha.py     # 终末地抽卡记录查询/更新/分页渲染
│       └── utils.py     # 终末地命令辅助函数
├── schemas/
│   ├── __init__.py      # 对外集中导出 Pydantic 模型
│   ├── binding.py       # 森空岛绑定角色/游戏列表结构
│   ├── cred.py          # CRED 凭证模型
│   ├── arknights/
│   │   ├── card.py      # ArkCard 角色卡片结构
│   │   ├── sign.py      # ArkSignResponse / ArkSignResult
│   │   ├── game_data.py # CharTable、GachaTable、GachaDetails 等游戏数据结构
│   │   ├── gacha/       # 明日方舟抽卡基础、卡池、统计模型
│   │   ├── rogue/       # 肉鸽基础数据、生涯统计、历史记录模型
│   │   └── models/      # 角色卡片的状态、干员、基建、招募、活动、皮肤等详细模型
│   └── endfield/
│       ├── card.py      # EndfieldCard 与终末地角色卡片结构
│       ├── sign.py      # EndfieldSignResponse
│       └── gacha/
│           ├── base.py       # EndfieldPoolType、角色/武器抽卡响应、Content API 模型
│           ├── pool.py       # EfGachaPoolInfo、保底/歪卡/武库配额统计
│           └── statistics.py # EfGroupedGachaRecord、分类统计、分页可见池计算
├── migrations/          # nonebot-plugin-orm/Alembic 迁移脚本
└── resources/
    ├── data/            # 内置数据快照（如 char_catalog.json）
    ├── fonts/           # 渲染字体
    ├── images/          # 内置图片资源（背景、职业、稀有度、终末地素材、抽卡装饰等）
    └── templates/       # Jinja2 HTML 模板与生成的 CSS
        ├── ark_card.html.jinja2
        ├── operator_roster.html.jinja2
        ├── endfield_card.html.jinja2
        ├── gacha.html.jinja2
        ├── gacha_macros.html.jinja2
        ├── ef_gacha.html.jinja2
        ├── ef_gacha_macros.html.jinja2
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

## 命令系统

命令树定义在 `nonebot_plugin_skland/matcher.py`，插件入口在 `nonebot_plugin_skland/__init__.py` 使用 `@skland.assign(...)` 分发到各 `commands/` handler。

主命令：

```text
skland [target]
sk [target]              # Alconna 别名
```

主要子命令：

```text
skland bind <token|cred> [-u]
skland qrcode
skland unbind
skland arksign sign [--all] [-u <uid>]
skland arksign status [--all]
skland arksign all
skland efsign sign [--all] [-u <uid>]
skland efsign status [--all]
skland efsign all
skland char update [--all]
skland sync [--img] [--data] [--force] [--update]
skland rogue [target] [--topic 傀影|水月|萨米|萨卡兹|界园|黑流树海]
skland rginfo <id> [-f]
skland gacha [target] [-b <begin>] [-l <limit>]
skland import <url>
skland campaign on|off|status
skland box [target] [-r <rarity>] [-p <profession>] [-n <name>]
skland book [target] [-r <rarity>] [-p <profession>] [-n <name>]
skland efcard [target] [-a] [-s]
skland efgacha [target] [-u] [-b <begin>] [-l <limit>]
```

内置快捷指令在 `hook.py` 启动时注册，并通过 `nonebot_plugin_alconna.command_manager` 持久化到插件缓存目录的 `shortcut.db`。当前包括：森空岛绑定、扫码绑定、森空岛解绑、明日方舟签到、签到详情、全体签到、全体签到详情、各肉鸽主题、角色更新、全体角色更新、资源更新、战绩详情、收藏战绩详情、方舟抽卡记录、导入抽卡记录、剿灭提醒、关闭剿灭提醒、干员盒、图鉴、终末地签到、终末地签到详情、终末地全体签到、终末地全体签到详情、`ef|zmd`、终末地抽卡记录、终末地抽卡更新。

## 核心实现说明

### 配置

配置模型在 `config.py`：

```python
class Config(BaseModel):
    skland: ScopedConfig = Field(default_factory=ScopedConfig)
```

`.env` 中使用 `skland__...` 形式配置。当前字段：

- `github_proxy_url`: GitHub 代理 URL。
- `github_token`: GitHub Token，用于缓解 GitHub API 限流。
- `check_res_update`: 启动时是否检查并下载图片资源。
- `background_source`: 明日方舟/终末地卡片背景来源，支持 `default` / `Lolicon` / `random` / `CustomSource`。
- `endfield_background_simple`: 是否默认启用终末地角色卡片简化背景。
- `rogue_background_source`: 肉鸽背景来源，支持 `default` / `rogue` / `Lolicon` / `CustomSource`。
- `argot_expire`: 暗语缓存过期时间（秒）。
- `gacha_render_max`: 明日方舟抽卡记录单图渲染卡池上限。
- `ef_gacha_render_max`: 终末地抽卡记录单图渲染各类别卡池上限。

资源路径：

- `RES_DIR`: 包内静态资源目录。
- `TEMPLATES_DIR`: 包内模板目录。
- `CACHE_DIR`: `nonebot-plugin-localstore` 插件缓存目录。
- `DATA_DIR`: `nonebot-plugin-localstore` 插件数据目录。
- `GACHA_DATA_PATH`: 明日方舟游戏数据缓存目录。

### 数据库模型

`model.py` 中有三个主要 ORM 模型：

- `SkUser`
  - 保存森空岛 `access_token`、`cred`、`cred_token`、`user_id`。
- `Character`
  - 保存用户绑定角色：`uid`、`role_id`、`app_code`、`channel_master_id`、`nickname`、`isdefault`。
  - `id` + `uid` 为复合主键。
- `GachaRecord`
  - 保存明日方舟与终末地抽卡记录。
  - `app_code` 区分 `arknights` / `endfield`。
  - `item_type` 区分 `char` / `weapon`。
  - `is_free` 用于终末地角色池免费抽记录。
  - 唯一约束为 `char_uid + app_code + gacha_ts + pos`。
- `CampaignReminder`
  - 保存用户剿灭奖励提醒开关、群聊推送 Target（JSON）与 @ 用的平台用户 ID。
  - `user_id` 外键关联 `SkUser`，解绑时级联删除。

新增或修改模型后需要添加迁移脚本。

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
- `endfield_card()`：终末地角色卡片数据。
- `endfield_sign()`：终末地签到。
- `get_ef_gacha_history()`：终末地角色池/武器池抽卡记录。
- `get_ef_gacha_content()`：终末地卡池 UP 内容。

`api/login.py` 的 `SklandLoginAPI` 负责 token/cred 互换、cred_token 刷新、二维码扫码登录、role token 获取等。

### Token 自动刷新

`utils.py` 提供四个装饰器：

- `refresh_access_token_if_needed`
- `refresh_cred_token_if_needed`
- `refresh_access_token_with_error_return`
- `refresh_cred_token_with_error_return`

命令 handler 通常使用前两者，在接口异常时通过消息反馈；定时任务使用 `*_with_error_return`，避免定时任务中直接发送消息。

刷新逻辑：

- `UnauthorizedException` 通常表示 `cred_token` 失效，使用 `SklandLoginAPI.refresh_token(user.cred)` 刷新。
- `LoginException` 通常表示 `cred` 失效，若有 `access_token`，通过 grant code 重新获取 cred。

### 游戏数据与资源

`data_source.py`：

- `GachaTableData`
  - 管理明日方舟 `gacha_table.json`、`character_table.json` 与 PRTS 卡池详情。
  - 使用 `GameResourceDownloader.check_update()` 比较版本。
  - `load(force=False)` 会按需下载、更新版本文件并解析数据。
- `EfGachaPoolTableData`
  - 从 `FrostN0v0/EndfieldGachaPoolTable` 拉取 `GachaPoolTable.json`。
  - 启动或同步数据时尝试覆盖下载；下载失败且本地有旧文件时使用本地缓存。
  - 提供 `get_pool(pool_id)` 为终末地抽卡渲染补充 UP 信息。

`hook.py` 启动时会加载 `gacha_table_data` 和 `ef_gacha_pool_data`。若 `check_res_update=True`，还会调用 `download_img_resource()` 检查并下载图片资源。

### 抽卡记录

明日方舟：

- `commands/gacha.py` 从接口拉取抽卡记录，或通过 `import_heybox_gacha_data()` 导入小黑盒导出数据。
- `utils.group_gacha_records()` 按卡池与时间戳分组，并补充 UP 干员、开放时间、卡池规则类型。
- `render.render_gacha_history()` 使用 `gacha.html.jinja2` 渲染。

### 干员盒 / 图鉴

- `commands/box.py`：`skland box`（仅已拥有）与 `skland book`（全图鉴，未拥有灰显）。
- `roster.py`：PRTS Half 框资源 URL、筛选与卡片组装；渲染 DTO（`RosterCard` 等）放此处，不进入 `schemas/`。
- 静态快照：`resources/data/char_catalog.json`（含 `sort_id` 实装序、技能 id、模组 `type_icon`）。新干员上线后需从 `character_table` / `uniequip_table` 与 PRTS 实装序重建该文件。
- 立绘：`char_skin/portrait/{skinId}`；图鉴未拥有用默认 `#1`，已拥有用玩家 `skinId`。
- `render.render_operator_roster()`：固定宽度长截图一页渲染全部匹配干员。因远程立绘/框体图数量大，**不走** htmlrender `template_to_pic` 默认的 `wait_until=networkidle`（弱网易 30s 超时）；改为 `get_new_page` + `domcontentloaded` + 图片 settle（失败图放行）+ 更长 timeout。
- 模板 `operator_roster.html.jinja2` 为 PRTS Half 半身像样式，使用内联自定义 CSS（不复用 Tailwind `index.css`），以对齐图鉴框体而非通用卡片面板。

终末地：

- `commands/endfield/gacha.py` 中 `EF_CHAR_POOL_TYPES` 包含 `STANDARD`、`SPECIAL`、`BEGINNER`、`JOINT`；武器池单独使用 `WEAPON`。
- `skland efgacha` 默认只从数据库缓存读取；首次使用或需要同步时使用 `-u` 拉取接口数据并去重保存。
- `utils.get_all_ef_gacha_records()` 会并发分页获取终末地抽卡记录。
- `utils.group_ef_gacha_records()` 将记录分为 `beginner_pools`、`standard_pools`、`special_pools`、`joint_pools`、`weapon_pools`。
- `EfGroupedGachaRecord` 负责各类统计：总抽数、六星平均抽数、保底、UP/歪卡、武库配额、可见卡池切片。
- `render.render_ef_gacha_history()` 根据是否存在联合寻访动态调整视口宽度；`-b` / `-l` 对各类别分别切片。

### 渲染系统

渲染入口在 `render.py`，都调用 `nonebot_plugin_htmlrender.template_to_pic()`。

主要函数：

- `render_ark_card()`：明日方舟角色卡片。
- `render_operator_roster()`：干员盒 / 图鉴 Half 网格长图。
- `render_ef_card()`：终末地角色卡片，支持 `show_all` 和 `simple` 背景。
- `render_gacha_history()`：明日方舟抽卡记录。
- `render_ef_gacha_history()`：终末地抽卡记录，支持分页切片与联合寻访宽度扩展。
- `render_rogue_card()` / `render_rogue_info()`：肉鸽战绩总览 / 单局详情。
- `render_clue_board()`：线索看板。

模板位于 `resources/templates/`，过滤器位于 `filters.py`。Tailwind 输出 CSS 为 `nonebot_plugin_skland/resources/templates/index.css`。

### 定时任务

`tasks.py` 注册三个 cron 任务：

```python
@scheduler.scheduled_job("cron", day_of_week="sun", hour="12,18", timezone=Asia/Shanghai, id="campaign_reminder")
async def run_campaign_reminder(): ...

@scheduler.scheduled_job("cron", hour=0, minute=15, id="daily_arksign")
async def run_daily_arksign(): ...

@scheduler.scheduled_job("cron", hour=0, minute=20, id="daily_efsign")
async def run_daily_efsign(): ...
```

- `campaign_reminder`：对已开启提醒的用户按群聊合并检测；同一群内未完成者合并为一条 @ 提醒消息。
- 签到结果分别写入插件缓存目录：

- `sign_result.json`
- `endfield_sign_result.json`

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
- `tests/test_ef_gacha_joint_pool.py` 覆盖终末地联合寻访分类、统计与模板渲染相关行为。
- `tests/test_campaign_reminder.py` 覆盖剿灭奖励完成判定、群聊合并消息与 Target 分组逻辑。
- `tests/test_operator_roster.py` 覆盖干员盒/图鉴筛选解析、box/book 组卡、技能专精与模组展示逻辑。
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

迁移脚本位于 `nonebot_plugin_skland/migrations/`。已有迁移包括初始表、抽卡记录表、`role_id`、模型类型修正、终末地抽卡支持等。

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
- 例外：干员盒/图鉴 Half 半身像模板为对齐 PRTS 图鉴框体，使用独立内联 CSS，不强制套用 Tailwind 卡片面板。

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

## 工作流

工作流：Plan 模式与 Code 模式

你有两种主要工作模式：**Plan** 与 **Code**。

### 何时使用

- 对 **trivial** 任务，可以直接给出答案，不必显式区分 Plan / Code。
- 对 **moderate / complex** 任务，必须使用 Plan / Code 工作流。

### 公共规则

- **首次进入 Plan 模式时**，需要简要复述：
  - 当前模式（Plan 或 Code）；
  - 任务目标；
  - 关键约束（语言 / 文件范围 / 禁止操作 / 测试范围等）；
  - 当前已知的任务状态或前置假设。
- Plan 模式中提出任何设计或结论之前，必须先阅读并理解相关代码或信息，禁止在未阅读代码的情况下提出具体修改建议。
- 之后仅在 **模式切换** 或 **任务目标/约束发生明显变化** 时，才需要再次复述，不必在每一条回复中重复。
- 不要擅自引入全新任务（例如只让我修一个 bug，却主动建议重写子系统）。
- 对于当前任务范围内的局部修复和补全（尤其是你自己引入的错误），不视为扩展任务，可以直接处理。
- 你**必须**等待我确认你的计划，你才能进入 Code 模式并开始实现。
- 当我在自然语言中使用 “实现”、“落地”、“按方案执行”、“开始写代码”、“帮我把方案 A 写出来” 等表述时：
  - 必须视为我在明确请求进入 **Code 模式**；
  - 在该回复中立即切换到 Code 模式并开始实现。
  - 禁止再次提出同一选择题或再次询问我是否同意该方案。

---

### Plan 模式（分析 / 对齐）

输入：用户的问题或任务描述。

在 Plan 模式中，你需要：

1. 自上而下分析问题，尽量找出根因和核心路径，而不是只对症状打补丁。
2. 明确列出关键决策点与权衡因素（接口设计、抽象边界、性能 vs 复杂度等）。
3. 给出 **1–3 个方案**，每个方案需是最为可行且最接近理想状态的，每个方案包含：
   - 概要思路；
   - 影响范围（涉及哪些模块 / 组件 / 接口）；
   - 优点与缺点；
   - 潜在风险；
   - 推荐的验证方式（应写哪些测试、跑哪些命令、观察哪些指标）。
4. 仅在 **缺失信息会阻碍继续推进或改变主要方案选择** 时，才提出澄清问题；
   - 避免为细节反复追问用户；
   - 若不得不做假设，需显式说明关键假设。
5. 避免给出本质相同的 Plan：
   - 如果新方案与上一版只有细节差异，只说明差异与新增内容即可。

**当以下条件满足时退出 Plan 模式：**

- 我明确选择了其中一个方案，或者
- 某个方案显然优于其他方案，你可以说明理由并主动选择。（如风险不可接受、明显违反关键约束等）

一旦满足条件：

- 你必须在 **下一条回复中直接进入 Code 模式**，并按选定方案实施；
- 除非在实施过程中发现新的硬性约束或重大风险，否则禁止继续停留在 Plan 模式上扩写原计划；
- 如因新约束被迫重新规划，应说明：
  - 为什么当前方案无法继续；
  - 需要新增的前提或决策是什么；
  - 新 Plan 与之前相比有哪些关键变化。

---

### Code 模式（按计划实施）

输入：已经确认或你基于权衡选择的方案与约束。

在 Code 模式中，你需要：

1. 进入 Code 模式后，本回复的主要内容必须是具体实现（代码、补丁、配置等），而不是继续长篇讨论计划。
2. 在给出代码前，简要说明：
   - 将修改哪些文件 / 模块 / 函数（真实路径或合理假定路径均可）；
   - 每个修改的大致目的（例如 `fix offset calculation`、`extract retry helper`、`improve error propagation` 等）。
3. 偏好 **充分最简、可审阅的修改**（Sufficient-Minimal Change）：
   - **充分性**：变更必须完整解决已证实的根因，而非仅消除表面症状。如果根因跨多个文件，那整组原子变更就是最简 —— 而非只改一处的 symptom patch；
   - **不可再简化**：在满足充分性的所有方案中，选择引入最少新概念（新类型、新抽象层、新依赖、新约定）的那个。如果去掉某个引入后变更仍然充分，则必须去掉；
   - **原子自洽**：变更作为一个整体必须将系统从一个自洽状态带到另一个自洽状态，不允许为了 diff 更小而产生中间不自洽的半成品；
   - 优先展示局部片段或 patch，而不是大段无标注的完整文件；如需展示完整文件，应标明关键变更区域。
4. 明确指出应该如何验证改动：
   - 建议运行哪些测试 / 命令；
   - 如有必要，给出新增 / 修改测试用例的草稿（代码使用 English）。
5. 如果在实现过程中发现原方案存在重大问题：
   - 暂停继续扩展该方案；
   - 切回 Plan 模式，说明原因并给出修订后的 Plan。

**输出应包括：**

- 做了哪些改动、位于哪些文件 / 函数 / 位置；
  - 不需要额外去检查行列位置，最多就报告符号名称即可。我有 IDE 可以代劳，你做就只是在增加回复延迟。
- 应该如何验证（测试、命令、人工检查步骤）；
- 任何已知限制或后续待办事项。

---

## 语言与编码风格

- 解释、讨论、分析、总结：使用 **简体中文**。
- 所有代码、注释、标识符（变量名、函数名、类型名等），以及 Markdown 代码块内的内容：全部使用 **English**，不得出现中文字符。
- 提交信息请按照当前 repo 的历史提交习惯，采用 gitmoji 规范
- Markdown 文档中：正文说明使用中文，代码块内全部内容使用 English。
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

## 其他风格与行为约定

- 不要拘泥于文书工作本身，表述到位即可，无需再产生更详细的解释或文档。
- 默认不要讲解基础语法、初级概念或入门教程；只有在我明确要求时，才用教学式解释。
- 优先把时间和字数用在：
  - 设计与架构；
  - 抽象边界；
  - 性能与并发；
  - 正确性与鲁棒性；
  - 可维护性与演进策略。
- 在没有必要澄清的重要信息缺失时，尽量减少无谓往返和问题式对话，直接给出高质量思考后的结论与实现建议。
- 如果一段话删掉后不影响我做决策，那就不要写。
  - 直接给出结论或方案，不要铺垫
  - 省略显而易见的上下文和已知信息
  - 只在对理解关键逻辑有帮助时才举例
  - 追问的代价小于猜错返工的代价时，追问；否则给出最佳判断并标注假设
