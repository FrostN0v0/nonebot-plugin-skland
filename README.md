<!-- markdownlint-disable MD033 MD036 MD041 MD046 -->
<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/FrostN0v0/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="300"  alt="NoneBotPluginLogo"></a>
  <br>
</div>

<div align="center">

# nonebot-plugin-skland

_✨ 通过森空岛查询游戏数据 ✨_

<h1>🚧 <bold>绝赞施工中</bold> 🚧</h1>

<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/FrostN0v0/nonebot-plugin-skland.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-skland">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-skland.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="python">
<br>
<a href="https://results.pre-commit.ci/latest/github/FrostN0v0/nonebot-plugin-skland/master">
    <img src="https://results.pre-commit.ci/badge/github/FrostN0v0/nonebot-plugin-skland/master.svg" alt="pre-commit.ci status">
</a>
<a href="https://registry.nonebot.dev/plugin/nonebot-plugin-skland:nonebot_plugin_skland">
  <img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fnbbdg.lgc2333.top%2Fplugin%2Fnonebot-plugin-skland" alt="NoneBot Registry" />
</a>
<a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv">
</a>
<a href="https://github.com/astral-sh/ruff">
<img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json" alt="ruff">
</a>
<a href="https://www.codefactor.io/repository/github/FrostN0v0/nonebot-plugin-skland"><img src="https://www.codefactor.io/repository/github/FrostN0v0/nonebot-plugin-skland/badge" alt="CodeFactor" />
</a>

</div>

## 📖 介绍

通过森空岛查询游戏数据

<img width="100%" src="https://starify.komoridevs.icu/api/starify?owner=FrostN0v0&repo=nonebot-plugin-skland" alt="starify" />

<details>
  <summary><kbd>Star History</kbd></summary>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=FrostN0v0/nonebot-plugin-skland&theme=dark&type=Date" />
    <img width="100%" src="https://star-history.com/#FrostN0v0/nonebot-plugin-skland&Date",alt="star history" />
  </picture>
</details>

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-skland

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

    pip install nonebot-plugin-skland
</details>
<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-skland
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-skland
</details>
<details>
<summary>conda</summary>

    conda install nonebot-plugin-skland
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_skland"]

</details>

## ⚙️ 配置

### 配置表

在 nonebot2 项目的`.env`文件中修改配置项

| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| 配置项 1 | 否 | 无 | 配置说明 |
| 配置项 2 | 否 | 无 | 配置说明 |

## 🎉 使用

> [!NOTE]
> 记得使用[命令前缀](https://nonebot.dev/docs/appendices/config#command-start-%E5%92%8C-command-separator)哦

### 🪧 指令表

| 指令 | 权限 | 参数 | 说明 |
|:-----:|:----:|:----:|:----:|
| 指令1 | 所有 | 无 | 指令说明 |
| 指令2 | 所有 | `无` or `@` | 指令说明 |

### 📸 效果图

![示例图1](docs/skland-1.png)

## 💖 鸣谢

- [`Alconna`](https://github.com/ArcletProject/Alconna): 简单、灵活、高效的命令参数解析器
- [`NoneBot2`](https://nonebot.dev/): 跨平台 Python 异步机器人框架

## 📋 TODO

- [x] 肉鸽战绩返回信息解析
- [ ] 渲染角色信息卡片
- [ ] 渲染肉鸽战绩卡片
- [ ] 完善指令逻辑
- [ ] 待补充
