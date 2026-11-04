# MAA 模块部署

本模块通过 MAA 原生 HTTP 轮询通信，不需要在用户电脑安装额外代理。公网网关和 NoneBot 是独立进程，共用 MAA 专用 SQLite 目录；不共用森空岛账号数据库。

协议依据：[MAA 远程控制协议](https://docs.maa.plus/zh-cn/protocol/remote-control-schema.html)、[QQ 群消息与按钮接口](https://bot.q.qq.com/wiki/develop/api-v2/autogen/api/v2_groups_group_openid_messages.post.html)。

## 插件配置

```bash
uv add 'nonebot-plugin-skland[maa]'
```

配置默认关闭。将 `maa` 合并进已有的 `SKLAND` JSON；保留其他配置：

```dotenv
SKLAND='{"maa":{"enabled":true,"public_url":"https://maa.example.com","data_dir":"/var/lib/skland-maa","binding_state_dir":"/var/lib/skland-maa-binding","binding_socket":"/var/lib/skland-maa-ipc/broker.sock"}}'
```

也可使用仓库约定的嵌套字段形式；与上面的 JSON 示例二选一，其他森空岛配置保持原值：

```dotenv
skland__maa__enabled=true
skland__maa__public_url=https://maa.example.com
skland__maa__data_dir=/var/lib/skland-maa
skland__maa__binding_state_dir=/var/lib/skland-maa-binding
skland__maa__binding_socket=/var/lib/skland-maa-ipc/broker.sock
```

| 字段 | 默认值 | 填写说明 |
| --- | --- | --- |
| `skland.maa.enabled` | `false` | 是否加载 MAA 命令、菜单、通知与清理任务 |
| `skland.maa.public_url` | 空字符串 | 外部 HTTPS 根地址，不带 `/maa/getTask`；回环 HTTP 仅供本地测试 |
| `skland.maa.data_dir` | localstore 插件数据目录下的 `maa/` | 与网关 `MAA_REMOTE_DATA_DIR` 指向同一绝对目录 |
| `skland.maa.binding_state_dir` | localstore 插件数据目录下的 `maa-binding/` | bot 私有目录，不能位于网关可写的目录树 |
| `skland.maa.binding_socket` | 未设置 | Unix socket 路径，未配置时网页绑定不可用 |

机器人需要 QQ 适配器、单聊与群消息事件、INTERACTION_CREATE 事件、Markdown/内嵌键盘权限。主动汇报还需要 QQ 主动消息权限，平台频控或禁言仍可能导致失败。普通用户可绑定自己的设备；证书状态查询仅超级用户可用，不出现在用户操作手册和按钮菜单。

模块关闭时不导入 QQ 适配器、不创建 MAA 数据或后台任务，不影响原有森空岛命令和其他适配器。

## 独立网关

在独立虚拟环境安装包含本模块的同一版本，**不要向网关环境复制 bot 的 `.env`、QQ 密钥或森空岛凭证**。查询该环境中的模块目录：

```bash
<GATEWAY_PYTHON> -c 'from importlib.metadata import distribution; print(distribution("nonebot-plugin-skland").locate_file("nonebot_plugin_skland/integrations/maa"))'
```

结果填入 `<MAA_MODULE_DIR>`。从该目录加载 `gateway:app`，不会导入 Skland 插件入口，不需要初始化 NoneBot：

```bash
MAA_REMOTE_DATA_DIR=<MAA_DATA_DIR> <GATEWAY_PYTHON> -m uvicorn --app-dir <MAA_MODULE_DIR> gateway:app --host 127.0.0.1 --port <GATEWAY_PORT> --workers 1 --limit-concurrency 24 --no-access-log --no-proxy-headers
```

使用 [gateway.service.example](../examples/maa/gateway.service.example) 配置独立服务。替换所有尖括号占位符后再安装；网关用户加入专用共享组，只授予 MAA 目录访问权限。bot 用户也需要加入该组。共享目录设为组可写并继承组（例如权限 `2770`），两进程使用 `UMask=0007`；数据库和截图为 `0660`。不要调整 bot 的全局运行用户或其他目录权限。

`<BOT_PRIVATE_DIR>` 指向 bot 私有配置所在目录，网关用户不可读取；`<CERTBOT_PRIVATE_DIR>` 指向 ACME 客户端私有目录。网关仅监听回环地址，由反向代理公开下面两个 POST 接口：

```text
/maa/getTask
/maa/reportStatus
```

连接密钥只保存哈希，首次连接绑定设备；汇报检查设备、任务归属及状态。上传大小不超过 12 MiB，截图解码后另有限制。单进程最多同时处理两份回报，网关服务限制进程资源。模板只限制网关服务，不修改 SSH、安全组或 bot 的权限。

## 网页绑定服务

网页服务与远控网关使用不同的 Unix 账户和组。按 [binding.service.example](../examples/maa/binding.service.example) 配置服务，监听回环 `<BINDING_PORT>`，通过 Nginx 精确公开 `/maa/bind` 与 `/maa/bind/`。
网页不读取绑定 SQLite、QQ 凭证或证书私钥，只能通过 Unix socket 调用 `submit`、`status`、`redeem`；创建申请与 QQ 确认由 bot 执行。

由管理员预先创建 `<BINDING_STATE_DIR>`（bot 所有，`0700`）及独立 `<BINDING_SOCKET_DIR>`（bot 所有、组为 `<BINDING_GROUP>`，`0750`），socket 填为该目录中的 `<BINDING_SOCKET>`。
网页用户不能写 socket 所在目录；bot 创建 socket 并设为 `0660`。目录及其父目录不能位于网关或网页可写的树中。
若 bot 服务启用了 `ProtectSystem`，仅为 bot 增加两个专用目录的写权限。无需改变 bot 的全局用户、森空岛数据权限或其他服务。

模板设置 CPU 25%、内存 128 MiB、并发 12，并对网页单独限流和限连接。网页每四秒查询一次，后台标签暂停，故障退避至三十秒，十分钟后停止。
绑定申请最多 100 份，每份最多三个浏览器；过期状态由 bot 定期清理。申请不是登录认证，必须由 QQ 发起者核对网页校验码；本人确认他人的网页仍可能误绑定。

启动 bot 后启动网页服务，未加载 broker 时网页会返回暂不可用。开启 QQ 群聊和单聊消息、按钮权限；确认消息发送失败时支持 `/MAA绑定 查询` 从原会话重新获取。
密钥仅在已确认浏览器领取一次，丢失后重新申请；首次连接有效期十五分钟，并校验申请中的设备标识符。现有已连接绑定继续可用。

`/超管菜单` 仅 QQ 私聊且 SUPERUSER 可用，列出本模块及 Skland 管理命令；不会加入用户帮助目录。

## HTTPS 与自动续期

以下模板不含真实地址、证书或部署路径：

- [nginx.conf.example](../examples/maa/nginx.conf.example)：TLS、精确路由、请求大小与连接限制；80 端口仅开放 ACME challenge。`limit_*_zone` 放在 Nginx 的 `http` 上下文。
- [renew.env.example](../examples/maa/renew.env.example)：续期脚本的证书、目录和命令字段。
- [renew_certificate.py](../examples/maa/renew_certificate.py)：调用 certbot 续期，成功更新证书后执行 Nginx reload，并发布不含证书正文的状态文件。
- [maa-cert-renew.service.example](../examples/maa/maa-cert-renew.service.example) 与 [maa-cert-renew.timer.example](../examples/maa/maa-cert-renew.timer.example)：每六小时检查，随机延迟最多十五分钟，关机错过后补执行。

填写这些参数：

| 占位符 | 填写内容 |
| --- | --- |
| `<MAA_HOST>` | 实际域名；使用 IP 证书时需选支持 IP 证书的 ACME 客户端配置 |
| `<CERT_NAME>` | certbot 中已有证书名称 |
| `<CERT_CHAIN_PATH>` / `<CERT_KEY_PATH>` | 证书链及私钥的绝对路径，仅用于 Nginx/续期环境 |
| `<ACME_WEBROOT>` | HTTP-01 challenge 文件目录 |
| `<GATEWAY_PORT>` | 与网关监听一致的回环端口 |
| `<MAA_DATA_DIR>` | bot 与网关共用的 MAA 专用目录 |
| `<CERTBOT_BIN>` / `<CERTBOT_LOG_DIR>` | certbot 可执行文件及专属日志目录，均填绝对路径 |
| `<NGINX_RELOAD_COMMAND>` | 本机成功部署证书后执行的一条 reload 命令，可执行文件填绝对路径，如 `/usr/bin/systemctl reload nginx`；参数含空格时加引号，不支持管道、重定向、变量展开或多条命令 |
| `<RENEW_ENV_PATH>` / `<RENEW_SCRIPT_PATH>` / `<ADMIN_PYTHON>` | root 专用续期配置、脚本和 Python 的绝对路径 |
| `<RENEW_STAGING_DIR>` | root 专用的状态暂存目录，与 `<MAA_DATA_DIR>` 位于同一文件系统，不能放入 bot/网关可写的目录树 |
| `<NGINX_LOG_DIR>` / `<NGINX_USER>` / `<NGINX_LOG_GROUP>` | Nginx 专属错误日志目录及其用户/组 |
| `<GATEWAY_USER>` / `<MAA_SHARED_GROUP>` | 网关系统用户及共享组 |

首次签发证书前，先使用仅含 80 端口 challenge 的配置。域名解析、HTTP-01 可达性和 certbot 账户邮箱由部署者配置，例如：

```bash
<CERTBOT_BIN> certonly --webroot -w <ACME_WEBROOT> -d <MAA_HOST> --email <ACME_EMAIL> --agree-tos --cert-name <CERT_NAME>
```

IP 证书的签发方式及更新频率按所选 ACME 客户端说明配置，不直接套用域名示例。签发成功后填写证书链和私钥路径，检查 Nginx 配置再加载 HTTPS。安装续期单元为 `maa-cert-renew.service` 和 `maa-cert-renew.timer`，确认 timer 已启用；证书目录及 renewal 配置保留给 ACME 客户端，私钥不放入 `SKLAND`。

续期环境文件仅 root 可读写；续期脚本、配置的可执行文件及其父目录由 root 管理，不允许 bot、网关用户或其他非特权用户修改。脚本以参数列表启动 certbot，reload 配置按单条命令解析并转义后交给 certbot 的部署 hook；不能填写 shell 脚本片段，复杂操作应放入 root 管理的独立可执行脚本。`<CERT_NAME>` 以字母或数字开头，其余字符限字母、数字、点、下划线和连字符。

状态文件写入共享目录并继承共享组，bot 只读状态。管理员可用 `/MAA证书` 查询剩余时间与检查异常，不向普通用户开放。此指令不会发起续期。

安装续期服务前，由 root 在自己管理的父目录中创建 `<RENEW_STAGING_DIR>`，所有者设为 root、权限设为 `0700`；其父目录也不得允许 bot/网关用户修改。脚本在这里安全创建随机临时文件，设置共享组与只读权限后，将文件原子替换到共享目录。发布时固定共享目录的文件描述符且拒绝目录符号链接，不会跟随预先植入的 `tls_status.tmp` 或 `tls_status.json` 链接写入其他文件。

## 三天保留

- bot 每小时清理三天前的任务、审计、消息去重和关联的通知记录，以及过期截图/临时文件。持久绑定不随任务过期。
- MAA 自身文件日志每天轮换，保留三天；不修改 bot 全局日志配置。
- 网关及续期服务使用 `skland-maa` journal 命名空间。将 [journal-retention.conf.example](../examples/maa/journal-retention.conf.example) 安装为 `/etc/systemd/journald@skland-maa.conf.d/retention.conf`，仅此命名空间保留三天。
- 将 [nginx-logrotate.example](../examples/maa/nginx-logrotate.example) 安装至 logrotate，确认每日调度。续期脚本每次检查时删除三天前的 certbot 日志。

部署后由管理员确认服务启动、证书签发及 timer 调度；这些模板不会在安装插件时自动修改系统服务。

## 从旧独立模块切换

本模块通过 `UserSession.user_id` 识别用户，不使用旧独立模块的 QQ OpenID 哈希命名方式。**不要直接覆盖旧部署或复用旧数据库并期待自动迁移**：使用新的 MAA 数据目录，按用户重新绑定，重新填写连接密钥后停用旧入口。没有自动数据库迁移，也不会修改森空岛绑定数据。

