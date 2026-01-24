<!-- markdownlint-disable MD028 MD033 MD036 MD041 MD046 -->
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
<summary>uv</summary>

    uv add nonebot-plugin-skland

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

|              配置项               | 必填  |   默认值    |               说明                |
| :-------------------------------: | :---: | :---------: | :-------------------------------: |
|    `skland__github_proxy_url`     |  否   |    `""`     |          GitHub 代理 URL          |
|      `skland__github_token`       |  否   |    `""`     |           GitHub Token            |
|    `skland__check_res_update`     |  否   |   `False`   |     是否在启动时检查资源更新      |
|    `skland__background_source`    |  否   | `"default"` |           背景图片来源            |
| `skland__rogue_background_source` |  否   |  `"rogue"`  |       肉鸽战绩背景图片来源        |
|      `skland__argot_expire`       |  否   |    `300`    |      暗语消息过期时间（秒）       |
|    `skland__gacha_render_max`     |  否   |    `30`     | 抽卡记录单图渲染上限（单位:卡池） |

> [!TIP]
> 以上配置项均~~没什么用~~按需填写，GitHub Token 用于解决 fetch_file_list 接口到达免费调用上限，但不会有那么频繁的更新频率，99.98%的概率是用不上的。~~只是因为我开发测试的时候上限了，所以有了这项~~,
>
> 本插件所使用的`干员半身像`、`技能图标`等资源，均优先调用本地，不存在则从网络请求获取，所以本地资源更新非必要选项，按需填写，不想过多请求网络资源可以自动或指令手动更新下载本地资源。

### background_source

`skland__background_source` 为背景图来源，可选值为字面量 `default` / `Lolicon` / `random` 或者结构 `CustomSource` 。 `Lolicon` 为网络请求获取随机带`arknights`tag 的背景图，`random`为从[默认背景目录](/nonebot_plugin_skland/resources/images/background/)中随机, `CustomSource` 用于自定义背景图。 默认为 `default`。

`rogue_background_source` 为肉鸽战绩背景图来源，可选值为字面量 `default` / `Lolicon` / `rogue` 或者结构 `CustomSource` 。 `rogue`为根据肉鸽主题提供的一套默认背景图。

以下是 `CustomSource` 用法示例

在配置文件中设置 `skland__background_source` 为 `CustomSource`结构的字典

<details>
  <summary>CustomSource配置示例</summary>

- 网络链接

  - `uri` 可为网络图片 API，只要返回的是图片即可
  - `uri` 也可以为 base64 编码的图片，如 `data:image/png;base64,xxxxxx` ~~（一般也没人这么干）~~

```env
skland__background_source = '{"uri": "https://example.com/image.jpg"}'
```

- 本地图片

> - `uri` 也可以为本地图片路径，如 `imgs/image.jpg`、`/path/to/image.jpg`
> - 如果本地图片路径是相对路径，会使用 [`nonebot-plugin-localstore`](https://github.com/nonebot/plugin-localstore) 指定的 data 目录作为根目录
> - 如果本地图片路径是目录，会随机选择目录下的一张图片作为背景图

```env
skland__background_source = '{"uri": "/imgs/image.jpg"}'
```

</details>

## 🎉 使用

> [!NOTE]
> 记得使用[命令前缀](https://nonebot.dev/docs/appendices/config#command-start-%E5%92%8C-command-separator)哦

### 🪧 指令总览

<details open>
<summary><b>🔐 账号管理</b></summary>

| 指令                           | 权限 | 说明                     |
| ------------------------------ | ---- | ------------------------ |
| `skland bind <token\|cred>`    | 所有 | 绑定森空岛账号           |
| `skland bind -u <token\|cred>` | 所有 | 更新绑定的 token 或 cred |
| `skland qrcode`                | 所有 | 扫码绑定森空岛账号       |
| `skland char update`           | 所有 | 更新森空岛绑定角色信息   |

**快捷指令：** `森空岛绑定` `扫码绑定` `角色更新`

</details>

<details open>
<summary><b>🎮 游戏信息</b></summary>

| 指令            | 权限 | 说明                   |
| --------------- | ---- | ---------------------- |
| `skland`        | 所有 | 查询默认角色信息卡片   |
| `skland @某人`  | 所有 | 查询指定用户的角色信息 |
| `skland <QQ号>` | 所有 | 查询指定QQ号的角色信息 |

</details>

<details open>
<summary><b>✍️ 每日签到</b></summary>

#### 明日方舟签到

| 指令                           | 权限     | 说明                      |
| ------------------------------ | -------- | ------------------------- |
| `skland arksign sign --all`    | 所有     | 签到所有绑定角色          |
| `skland arksign sign -u <uid>` | 所有     | 指定 UID 角色签到         |
| `skland arksign status`        | 所有     | 查询个人角色签到状态      |
| `skland arksign all`           | 超级用户 | 签到所有绑定到 bot 的角色 |
| `skland arksign status --all`  | 超级用户 | 查询所有角色的签到状态    |

**快捷指令：** `明日方舟签到` `签到详情` `全体签到` `全体签到详情`

#### 终末地签到

| 指令                           | 权限     | 说明                      |
| ------------------------------ | -------- | ------------------------- |
| `skland zmdsign sign --all`    | 所有     | 签到所有绑定角色          |
| `skland zmdsign sign -u <uid>` | 所有     | 指定 UID 角色签到         |
| `skland zmdsign status`        | 所有     | 查询个人角色签到状态      |
| `skland zmdsign all`           | 超级用户 | 签到所有绑定到 bot 的角色 |
| `skland zmdsign status --all`  | 超级用户 | 查询所有角色的签到状态    |

**快捷指令：** `终末地签到` `终末地签到详情` `终末地全体签到` `终末地全体签到详情`

</details>

> [!TIP]
> 插件会在每天 00:15 自动为所有明日方舟绑定角色签到，00:20 自动为所有终末地绑定角色签到，一般无需手动签到

<details open>
<summary><b>🎲 肉鸽战绩</b></summary>

| 指令                          | 权限 | 说明                       |
| ----------------------------- | ---- | -------------------------- |
| `skland rogue`                | 所有 | 查询默认角色的最新肉鸽战绩 |
| `skland rogue @某人`          | 所有 | 查询指定用户的肉鸽战绩     |
| `skland rogue --topic <主题>` | 所有 | 查询指定主题的肉鸽战绩     |
| `skland rginfo <战绩id>`      | 所有 | 查询最近战绩的详细信息     |
| `skland rginfo <战绩id> -f`   | 所有 | 查询收藏战绩的详细信息     |

**主题选项：** `傀影` `水月` `萨米` `萨卡兹` `界园`

**快捷指令：** `战绩详情` `收藏战绩详情` `傀影肉鸽` `水月肉鸽` `萨米肉鸽` `萨卡兹肉鸽` `界园肉鸽`

</details>

> [!TIP]
> 查询战绩详情时需要回复一条通过肉鸽战绩查询获取的图片消息

<details open>
<summary><b>🎰 抽卡记录</b></summary>

| 指令                               | 权限 | 说明                   |
| ---------------------------------- | ---- | ---------------------- |
| `skland gacha`                     | 所有 | 查询完整抽卡记录       |
| `skland gacha -b <起始id>`         | 所有 | 从指定位置开始查询     |
| `skland gacha -l <结束id>`         | 所有 | 查询到指定位置结束     |
| `skland gacha -b <起始> -l <结束>` | 所有 | 查询指定范围的抽卡记录 |
| `skland import <url>`              | 所有 | 导入小黑盒抽卡记录     |

**快捷指令：** `方舟抽卡记录` `导入抽卡记录`

</details>

> [!TIP]
> 抽卡记录使用提示：
>
> - 支持指定范围查询，如 `skland gacha -b -3` 查询倒数 3 个卡池
> - 或者 `skland gacha -b 3 -l 25` 查询第 3 到 25 个卡池
> - 导入记录时，在小黑盒抽卡分析页底部点击`数据管理`导出并复制链接
> - 单页卡池数超过配置的 `skland__gacha_render_max` 会输出多张图片

<details open>
<summary><b>🔧 资源管理</b></summary>

| 指令                   | 权限     | 说明                   |
| ---------------------- | -------- | ---------------------- |
| `skland sync`          | 超级用户 | 同时更新图片和数据资源 |
| `skland sync --img`    | 超级用户 | 仅更新图片资源         |
| `skland sync --data`   | 超级用户 | 仅更新数据资源         |
| `skland sync --force`  | 超级用户 | 强制更新，忽略版本检查 |
| `skland sync --update` | 超级用户 | 覆盖已存在的文件       |

**快捷指令：** `资源更新`

</details>

> [!TIP]
> 资源更新选项说明：
>
> - 可以组合使用选项，如 `skland sync --img --force --update`
> - 图片资源包括干员立绘、技能图标等，数据资源包括卡池数据、角色数据等
> - 默认跳过已存在的文件，使用 `--update` 可强制覆盖
> - 本地资源优先，不存在时从网络获取，非必要无需更新

<details>
<summary><b>🎨 暗语功能</b></summary>

暗语功能由 [nonebot-plugin-argot](https://github.com/KomoriDev/nonebot-plugin-argot) 提供支持

**使用方法：** 回复插件渲染的图片消息，发送对应的暗语指令

| 暗语指令     | 对象     | 说明           |
| ------------ | -------- | -------------- |
| `background` | 信息卡片 | 查看卡片背景图 |
| `clue`       | 游戏信息 | 查看角色线索板 |

</details>

### 🎯 快捷指令速查

<details>
<summary>查看所有快捷指令</summary>

| 触发词               | 执行指令                      | 说明               |
| -------------------- | ----------------------------- | ------------------ |
| `森空岛绑定`         | `skland bind`                 | 绑定账号           |
| `扫码绑定`           | `skland qrcode`               | 扫码绑定           |
| `明日方舟签到`       | `skland arksign sign --all`   | 签到所有角色       |
| `签到详情`           | `skland arksign status`       | 个人签到状态       |
| `全体签到`           | `skland arksign all`          | 全部角色签到       |
| `全体签到详情`       | `skland arksign status --all` | 全部签到状态       |
| `终末地签到`         | `skland zmdsign sign --all`   | 终末地签到         |
| `终末地签到详情`     | `skland zmdsign status`       | 终末地签到状态     |
| `终末地全体签到`     | `skland zmdsign all`          | 终末地全部签到     |
| `终末地全体签到详情` | `skland zmdsign status --all` | 终末地全部签到状态 |
| `角色更新`           | `skland char update`          | 更新角色信息       |
| `资源更新`           | `skland sync`                 | 更新资源文件       |
| `界园肉鸽`           | `skland rogue --topic 界园`   | 界园主题战绩       |
| `萨卡兹肉鸽`         | `skland rogue --topic 萨卡兹` | 萨卡兹主题战绩     |
| `萨米肉鸽`           | `skland rogue --topic 萨米`   | 萨米主题战绩       |
| `水月肉鸽`           | `skland rogue --topic 水月`   | 水月主题战绩       |
| `傀影肉鸽`           | `skland rogue --topic 傀影`   | 傀影主题战绩       |
| `战绩详情`           | `skland rginfo`               | 查询战绩详情       |
| `收藏战绩详情`       | `skland rginfo -f`            | 查询收藏战绩       |
| `方舟抽卡记录`       | `skland gacha`                | 查询抽卡记录       |
| `导入抽卡记录`       | `skland import`               | 导入抽卡数据       |

</details>

### 🪄 自定义快捷指令

基于 [Alconna 快捷指令](https://nonebot.dev/docs/best-practice/alconna/command#command%E7%9A%84%E4%BD%BF%E7%94%A8) 实现

<details>
<summary>点击查看详细说明</summary>

**语法：**

```bash
# 添加快捷指令
/skland --shortcut <自定义指令> <目标指令>

# 删除快捷指令
/skland --shortcut delete <自定义指令>

# 列出所有快捷指令
/skland --shortcut list
```

**示例：**

```bash
# 添加一个签到快捷指令
用户: /skland --shortcut /兔兔签到 "/skland arksign sign --all"
Bot: skland::skland 的快捷指令: "/兔兔签到" 添加成功

# 添加一个查询战绩的快捷指令
用户: /skland --shortcut 查战绩 "skland rogue"
Bot: skland::skland 的快捷指令: "查战绩" 添加成功
```

</details>

> [!NOTE]
>
> - 自定义指令不自动带命令前缀，需要时请手动添加
> - 指令中包含空格时，需要用引号 `""` 包裹

> [!NOTE]
> Token 获取相关文档还没写~~才不是懒得写~~
>
> 可以参考[`token获取`](https://docs.qq.com/doc/p/2f705965caafb3ef342d4a979811ff3960bb3c17)获取
>
> 本插件支持 cred 和 token 两种方式手动绑定，使用二维码绑定时会提供 token，请勿将 token 提供给不信任的 Bot 所有者

### 📸 效果图

<details id="效果图">
  <summary>🔮 游戏信息</summary>

![示例图1](docs/example_1.png)

</details>

<details>
  <summary>🫖 肉鸽战绩</summary>

![示例图2](docs/example_2.png)

</details>

<details>
  <summary>🏆 战绩详情</summary>

![示例图3](docs/example_3.png)

</details>

<details id="游戏信息">
  <summary>🕵️‍♀ 线索板</summary>

![线索板](docs/clue_board.png)

</details>

<details>
  <summary>🦭 抽卡记录</summary>

![抽卡记录](docs/gacha_record.png)

</details>

## 💖 鸣谢

- [`Alconna`](https://github.com/ArcletProject/Alconna): 简单、灵活、高效的命令参数解析器
- [`NoneBot2`](https://nonebot.dev/): 跨平台 Python 异步机器人框架
- [`yuanyan3060/ArknightsGameResource`](https://github.com/yuanyan3060/ArknightsGameResource): 明日方舟常用素材
- [`KomoriDev/Starify`](https://github.com/KomoriDev/Starify)：超棒的 GitHub Star Trace 工具 🌟📈
- [`KomoriDev/nonebot-plugin-argot`](https://github.com/KomoriDev/nonebot-plugin-argot): 优秀的 NoneBot2 暗语支持

### 贡献者们

<a href="https://github.com/FrostN0v0/nonebot-plugin-skland/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=FrostN0V0/nonebot-plugin-skland&max=100" alt="contributors" />
</a>

## 📢 声明

本插件仅供学习交流使用，数据由 [森空岛](https://skland.com/) 提供，请勿用于商业用途。

使用过程中，任何涉及个人账号隐私信息（如账号 token、cred 等）的数据，请勿提供给不信任的 Bot 所有者（尤其是 token）。

## 📋 TODO

- [x] 完善用户接口返回数据解析
- [x] 使用[`nonebot-plugin-htmlrender`](https://github.com/kexue-z/nonebot-plugin-htmlrender)渲染信息卡片
- [x] 从[`yuanyan3060/ArknightsGameResource`](https://github.com/yuanyan3060/ArknightsGameResource)下载游戏数据、检查数据更新
- [x] 绘制渲染粥游信息卡片
- [x] 支持扫码绑定
- [x] 优化资源获取形式
- [x] 完善肉鸽战绩返回信息解析
- [x] 绘制渲染肉鸽战绩卡片
- [x] 粥游签到自动化
- [x] 实现抽卡记录获取及渲染
- [x] 支持抽卡记录导入(从小黑盒)
- [x] 抽卡记录分页
- [ ] 实现 box 查询
- [ ] 实现图鉴查询
- [ ] 完善多服账号管理
- [ ] ~~扬了不必要的 💩~~
- [ ] 待补充，欢迎 pr
