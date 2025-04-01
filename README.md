<!-- markdownlint-disable MD033 MD036 MD041 MD046 -->
<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/FrostN0v0/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="300"  alt="NoneBotPluginLogo"></a>
  <br>
</div>

<div align="center">

# nonebot-plugin-skland

_✨ 通过森空岛查询游戏数据 ✨_

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

<br />
<a href="#-效果图">
  <strong>📸 演示与预览</strong>
</a>
&nbsp;&nbsp;|&nbsp;&nbsp;
<a href="#-安装">
  <strong>📦️ 下载插件</strong>
</a>
&nbsp;&nbsp;|&nbsp;&nbsp;
<a href="https://qm.qq.com/q/bAXUZu1BdK" target="__blank">
  <strong>💬 加入交流群</strong>
</a>

</div>

## 📖 介绍

通过森空岛查询游戏数据

> [!NOTE]
> 本插件存在大量未经验证的数据结构~~以及 💩 山~~
>
> 如在使用过程中遇到问题，欢迎提 [issue](https://github.com/FrostN0v0/nonebot-plugin-skland/issues/new/choose) 帮助改进项目

<img width="100%" src="https://starify.komoridevs.icu/api/starify?owner=FrostN0v0&repo=nonebot-plugin-skland" alt="starify" />

<details>
  <summary><kbd>Star History</kbd></summary>
  <picture>
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=FrostN0v0/nonebot-plugin-skland&type=Date&theme=dark" />
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

|           配置项            | 必填 |   默认值    |       说明       |
| :-------------------------: | :--: | :---------: | :--------------: |
| `skland__github_proxy_url`  |  否  |    `""`     | GitHub 代理 URL  |
|   `skland__github_token`    |  否  |    `""`     |   GitHub Token   |
| `skland__check_res_update`  |  否  |   `True`    | 是否检查资源更新 |
| `skland__background_source` |  否  | `"default"` |   背景图片来源   |

> [!TIP]
> 以上配置项均~~没什么用~~按需填写，GitHub Token 用于解决 fetch_file_list 接口到达免费调用上限，但不会有那么频繁的更新频率，99.98%的概率是用不上的。~~只是因为我开发测试的时候上限了，所以有了这项~~

### background_source

`skland__background_source` 为背景图来源，可选值为字面量 `default` / `Lolicon` / `random` 或者结构 `CustomSource` 。 `Lolicon` 为网络请求获取随机带`arknights`tag 的背景图，`random`为从[默认背景目录](/nonebot_plugin_skland/resources/images/background/)中随机, `CustomSource` 用于自定义背景图。 默认为 `default`。

以下是 `CustomSource` 用法

在配置文件中设置 `xxx_background_source` 为 `CustomSource`结构的字典

<details>
  <summary>CustomSource配置示例</summary>

- 网络链接

  - `uri` 可为网络图片 API，只要返回的是图片即可
  - `uri` 也可以为 base64 编码的图片，如 `data:image/png;base64,xxxxxx` ~~（一般也没人这么干）~~

```env
sign_background_source = '{"uri": "https://example.com/image.jpg"}'
```

- 本地图片

> [!TIP]
>
> - `uri` 也可以为本地图片路径，如 `imgs/image.jpg`、`/path/to/image.jpg`
> - 如果本地图片路径是相对路径，会使用 [`nonebot-plugin-localstore`](https://github.com/nonebot/plugin-localstore) 指定的 data 目录作为根目录
> - 如果本地图片路径是目录，会随机选择目录下的一张图片作为背景图

```env
sign_background_source = '{"uri": "/imgs/image.jpg"}'
```

</details>

## 🎉 使用

> [!NOTE]
> 记得使用[命令前缀](https://nonebot.dev/docs/appendices/config#command-start-%E5%92%8C-command-separator)哦

### 🪧 指令表

|           指令            | 权限 |       参数        |           说明            |
| :-----------------------: | :--: | :---------------: | :-----------------------: |
|         `skland`          | 所有 |     无 or `@`     |       角色信息卡片        |
|       `skland bind`       | 所有 | `token` or `cred` |      绑定森空岛账号       |
|     `skland bind -u`      | 所有 | `token` or `cred` | 更新绑定的 token 或 cred  |
|      `skland qrcode`      | 所有 |        无         |    扫码绑定森空岛账号     |
|     `skland arksign`      | 所有 |        无         |       明日方舟签到        |
| `skland arksign -u <uid>` | 所有 |       `uid`       | 指定绑定角色 UID 进行签到 |
|  `skland arksign --all`   | 所有 |        无         |     签到所有绑定角色      |
|   `skland char update`    | 所有 |        无         |  更新森空岛绑定角色信息   |
|      `skland rogue`       | 所有 |  `@` \| `topic`   |  肉鸽战绩查询(暂未完成)   |

> [!NOTE]
> Token 获取相关文档还没写~~才不是懒得写~~
>
> 可以参考[`token获取`](https://docs.qq.com/doc/p/2f705965caafb3ef342d4a979811ff3960bb3c17)获取
>
> 本插件支持 cred 和 token 两种方式手动绑定，使用二维码绑定时会提供 token，请勿将 token 提供给不信任的 Bot 所有者

### 🎯 快捷指令

|    触发词    |           执行指令            |
| :----------: | :---------------------------: |
|  森空岛绑定  |         `skland bind`         |
|   扫码绑定   |        `skland qrcode`        |
| 明日方舟签到 |       `skland arksign`        |
|  萨卡兹肉鸽  | `skland rogue --topic 萨卡兹` |
|   萨米肉鸽   |  `skland rogue --topic 萨米`  |
|   角色更新   |     `skland char update`      |

### 📸 效果图

![示例图1](docs/example.png)

## 💖 鸣谢

- [`Alconna`](https://github.com/ArcletProject/Alconna): 简单、灵活、高效的命令参数解析器
- [`NoneBot2`](https://nonebot.dev/): 跨平台 Python 异步机器人框架
- [`yuanyan3060/ArknightsGameResource`](https://github.com/yuanyan3060/ArknightsGameResource): 明日方舟常用素材
- [`KomoriDev/Starify`](https://github.com/KomoriDev/Starify)：超棒的 GitHub Star Trace 工具 🌟📈

## 📢 声明

本插件仅供学习交流使用，数据由 [森空岛](https://skland.com/) 提供，请勿用于商业用途。

使用过程中，任何涉及个人账号隐私信息（如账号 token、cred 等）的数据，请勿提供给不信任的 Bot 所有者（尤其是 token）。

## 📋 TODO

- [x] 完善用户接口返回数据解析
- [x] 使用[`nonebot-plugin-htmlrender`](https://github.com/kexue-z/nonebot-plugin-htmlrender)渲染信息卡片
- [x] 从[`yuanyan3060/ArknightsGameResource`](https://github.com/yuanyan3060/ArknightsGameResource)下载游戏数据、检查数据更新
- [x] 绘制渲染粥游信息卡片
- [ ] 粥游签到自动化
- [ ] 细化粥游信息卡片的部分信息展示
- [ ] 其余接口获取且有明确 ID 可命名的图片，优先调用本地图片，请求后缓存到本地（例如[肉鸽物品获取](https://web.hycdn.cn/arknights/game/assets/roguelike_item/rogue_3_relic_legacy_169.png)）
- [ ] 完善肉鸽战绩返回信息解析
- [ ] 绘制渲染肉鸽战绩卡片
- [ ] ~~扬了不必要的 💩~~
- [ ] 待补充
