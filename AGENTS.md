# AGENTS.md

本文档为 AI 编程代理（如 GitHub Copilot、Claude 等）提供项目上下文和开发指南。

## 项目概述

**nonebot-plugin-skland** 是一个基于 NoneBot2 框架的 Python 插件，用于通过森空岛（Skland）API 查询鹰角网络旗下游戏的数据，目前支持：

- **明日方舟（Arknights）**：角色信息卡片、签到、肉鸽战绩、抽卡记录
- **终末地（Endfield）**：签到功能

## 技术栈

- **Python**: >=3.10
- **框架**: NoneBot2 + nonebot-plugin-alconna（命令解析）
- **数据库**: SQLAlchemy ORM（通过 nonebot-plugin-orm）
- **渲染**: nonebot-plugin-htmlrender（Jinja2 模板 + Tailwind CSS）
- **定时任务**: nonebot-plugin-apscheduler
- **HTTP 客户端**: httpx

## 目录结构

```text
nonebot_plugin_skland/
├── __init__.py          # 插件入口，命令处理器注册
├── matcher.py           # Alconna 命令定义和快捷指令
├── tasks.py             # 定时任务（每日签到）
├── config.py            # 配置管理，数据加载
├── model.py             # SQLAlchemy ORM 模型（SkUser, Character, GachaRecord）
├── db_handler.py        # 数据库操作函数
├── api/
│   ├── __init__.py      # API 模块导出
│   ├── request.py       # SklandAPI - 森空岛数据接口（签到、角色信息等）
│   └── login.py         # SklandLoginAPI - 登录认证接口
├── commands/            # 命令处理器模块
│   ├── __init__.py      # 模块导出
│   ├── card.py          # 角色卡片查询处理
│   ├── bind.py          # 绑定和二维码登录
│   ├── char.py          # 角色信息更新
│   ├── sync.py          # 资源同步
│   ├── rogue.py         # 肉鸽战绩查询
│   ├── gacha.py         # 抽卡记录查询和导入
│   ├── arksign.py       # 明日方舟签到
│   └── zmdsign.py       # 终末地签到
├── schemas/             # Pydantic 数据模型
│   ├── __init__.py      # 模块导出（向后兼容）
│   ├── binding.py       # 绑定角色数据
│   ├── cred.py          # 认证凭据
│   ├── arknights/       # 明日方舟数据模型
│   │   ├── __init__.py  # 导出所有模型
│   │   ├── card.py      # 角色卡片（ArkCard）
│   │   ├── sign.py      # 签到响应（ArkSignResponse）
│   │   ├── game_data.py # 游戏数据（CharTable, GachaDetails）
│   │   ├── gacha/       # 抽卡相关模型
│   │   │   ├── base.py      # 基础类型（GachaInfo, GachaPull 等）
│   │   │   ├── pool.py      # 卡池（GachaPool）
│   │   │   └── statistics.py # 统计（GroupedGachaRecord）
│   │   ├── rogue/       # 肉鸽相关模型
│   │   │   ├── data.py      # 基础数据（Topics, RogueData）
│   │   │   ├── career.py    # 生涯统计（RogueCareer）
│   │   │   └── history.py   # 历史记录（RogueHistory）
│   │   └── models/      # 详细数据模型
│   │       ├── status.py    # 状态信息
│   │       ├── chars.py     # 角色信息
│   │       ├── building.py  # 基建信息
│   │       └── ...          # 其他模型
│   └── endfield/        # 终末地数据模型
│       ├── __init__.py
│       └── endfield_sign.py
├── render.py            # HTML 渲染函数
├── filters.py           # Jinja2 模板过滤器
├── utils.py             # 工具函数（Token刷新装饰器、资源下载等）
├── download.py          # 游戏资源下载器
├── exception.py         # 自定义异常类
├── hook.py              # 启动/关闭钩子
├── extras.py            # 帮助菜单数据
├── migrations/          # 数据库迁移脚本
└── resources/
    ├── fonts/           # 字体文件
    ├── images/          # 图片资源
    └── templates/       # Jinja2 HTML 模板 + CSS
```

## 核心模块说明

### 命令系统

命令定义和处理器分布在以下模块中：

- **`matcher.py`**: Alconna 命令定义和快捷指令

```python
skland_command = Alconna(
    "skland",
    Subcommand("bind", ...),      # 绑定账号
    Subcommand("qrcode", ...),    # 扫码绑定
    Subcommand("arksign", ...),   # 明日方舟签到
    Subcommand("zmdsign", ...),   # 终末地签到
    Subcommand("rogue", ...),     # 肉鸽战绩
    Subcommand("gacha", ...),     # 抽卡记录
    # ...
)
skland = on_alconna(skland_command, ...)
```

- **`__init__.py`**: 命令处理器注册，使用 `@skland.assign("subcommand.action")` 装饰器
- **`commands/`**: 按功能划分的命令处理逻辑

### 定时任务 (`tasks.py`)

定时任务从 `__init__.py` 中提取，独立管理：

```python
@scheduler.scheduled_job("cron", hour=0, minute=15, id="daily_arksign")
async def run_daily_arksign():
    # 每日 00:15 执行明日方舟签到
    ...

@scheduler.scheduled_job("cron", hour=0, minute=20, id="daily_zmdsign")
async def run_daily_zmdsign():
    # 每日 00:20 执行终末地签到
    ...
```

### API 请求签名 (`api/request.py`)

森空岛 API 需要特殊的请求签名：

```python
# 签名流程
1. 构建 header_ca（包含 timestamp、platform 等）
2. 拼接 secret = path + query + timestamp + header_ca_str
3. HMAC-SHA256(cred_token, secret) -> hex_secret
4. MD5(hex_secret) -> signature
```

### Token 自动刷新 (`utils.py`)

提供装饰器自动处理 Token 失效：

- `@refresh_access_token_if_needed` - 刷新 access_token
- `@refresh_cred_token_if_needed` - 刷新 cred_token
- `@refresh_*_with_error_return` - 错误时返回错误信息而非发送消息

### 数据库模型 (`model.py`)

三个主要模型：

- `SkUser` - 用户信息（access_token, cred, cred_token）
- `Character` - 绑定角色（uid, app_code, nickname）
- `GachaRecord` - 抽卡记录

### 渲染系统

1. **模板**: `resources/templates/*.html.jinja2`
2. **样式**: 使用 Tailwind CSS，通过 `npx tailwindcss` 编译
3. **渲染**: `nonebot_plugin_htmlrender.template_to_pic()`

## 开发规范

### 代码风格

- 使用 Ruff 进行代码检查和格式化
- 行长度限制: 120 字符
- 目标 Python 版本: 3.10+

```bash
# 格式化代码
uvx ruff format

# 检查代码
uvx ruff check
```

### 添加新功能的一般流程

1. **定义数据模型**: 在 `schemas/arknights/` 或 `schemas/endfield/` 中创建 Pydantic 模型
2. **实现 API 调用**: 在 `api/request.py` 中添加方法
3. **添加命令处理**: 在 `commands/` 中创建或扩展处理模块
4. **注册命令**: 在 `matcher.py` 中定义子命令，在 `__init__.py` 中注册处理器
5. **添加快捷指令**: 使用 `skland.shortcut()` 注册
6. **更新文档**: 同步更新 `extras.py` 和 `README.md`

### 添加新游戏支持

参考 `endfield/` 目录结构：

1. 在 `schemas/` 下创建游戏目录和数据模型
2. 在 `api/request.py` 添加 API 方法
3. 在 `db_handler.py` 添加数据库查询函数
4. 在 `commands/` 中添加命令处理模块
5. 在 `matcher.py` 和 `__init__.py` 中添加命令和处理器

## 常用命令

```bash
# 安装依赖
uv sync

# 运行 Bot
nb run

# 编译 Tailwind CSS
pnpm run build_css

# 构建发布包
uv build
```

## 数据库迁移

使用 Alembic（通过 nonebot-plugin-orm）：

```bash
# 创建迁移
nb orm revision --message "description"

# 应用迁移
nb orm upgrade
```

## 注意事项

1. **Token 安全**: 用户的 access_token 和 cred 是敏感信息，绑定命令仅允许私聊使用
2. **API 限流**: 森空岛 API 有请求频率限制，批量操作需注意间隔
3. **资源缓存**: 图片资源优先使用本地缓存，不存在时从网络获取
4. **错误处理**: 使用自定义异常类（`RequestException`, `LoginException`, `UnauthorizedException`）

## 相关资源

- [NoneBot2 文档](https://nonebot.dev/)
- [Alconna 文档](https://arclet.top/tutorial/alconna/v1.html)
- [森空岛](https://skland.com/)
- [游戏资源仓库](https://github.com/yuanyan3060/ArknightsGameResource)
