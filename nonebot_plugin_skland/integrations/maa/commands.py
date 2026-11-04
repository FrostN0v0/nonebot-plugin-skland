"""Private-chat command policy, independently testable without QQ networking."""

import json
from urllib.parse import urlsplit

from .core import RemoteError

HELP = (
    "【MAA 远程管理】\n"
    "私聊或群聊发送 /maa，使用竖版按钮菜单。\n"
    "/MAA绑定 — 网页填写设备标识符，QQ 确认后在原浏览器领取设置\n"
    "/MAA状态 — 设备在线状态\n"
    "/MAA 心跳 — 查询远程任务是否空闲\n"
    "/MAA 开始 一键长草 — 执行本机预设\n"
    "/MAA 开始 刷理智 — 支持唤醒、基建、公招、信用、领奖、肉鸽\n"
    "/MAA截图 — 获取模拟器截图\n"
    "/MAA停止 — 请求停止并取消服务器待领取任务\n"
    "/MAA结果 — 查看最近指令结果和截图\n"
    "/MAA解绑 — 撤销连接密钥\n"
    "任务参数沿用 MAA 本机配置；执行前请检查理智药、源石、公招和购物设置。"
    "群内请求的状态、结果与截图会显示在当前群。"
)


def validate_base_url(value):
    message = "管理员需配置 HTTPS 的 skland.maa.public_url 根地址（本地测试可用回环 HTTP）。"
    try:
        parsed = urlsplit(value)
        parsed.port  # Validate malformed and out-of-range ports as well.
    except ValueError:
        raise RemoteError(message) from None
    local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if (
        not parsed.netloc
        or not parsed.hostname
        or parsed.path not in {"", "/"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or "?" in value
        or "#" in value
        or parsed.scheme not in {"http", "https"}
        or (parsed.scheme == "http" and not local)
    ):
        raise RemoteError(message)
    return value.rstrip("/")


class Commands:
    def __init__(self, store, public_url):
        self.store = store
        self.public_url = public_url

    def handle(
        self,
        operation,
        private,
        owner,
        message_id=None,
        argument="",
        superuser=False,
        origin=None,
    ):
        if operation == "管理":
            return HELP, None
        if message_id and not self.store.claim_message(owner, message_id):
            return "这条消息已经处理过，请发送 /maa 查看 查询。", None
        if operation == "证书":
            if not superuser:
                return "该操作仅限超级用户。", None
            try:
                state = json.loads((self.store.directory / "tls_status.json").read_text(encoding="utf-8"))
                hours = max(0, int((state["expires_at"] - self.store.clock()) / 3600))
                stale = self.store.clock() - state["checked_at"] > 12 * 3600
                warning = state["warning"] or stale or hours < 36
                return (
                    f"HTTPS 证书剩余约 {hours} 小时。\n自动续期每六小时检查一次。\n"
                    + ("检查异常或证书临近到期，请管理员查看续期服务日志。" if warning else "最近一次续期检查正常。"),
                    None,
                )
            except (OSError, ValueError, KeyError, TypeError):
                return "证书检查信息暂不可用，请管理员查看续期服务。", None
        if operation == "解绑" and not private:
            return (
                "绑定配置和解绑仅限私聊，请私聊机器人发送 /MAA绑定 或 /MAA解绑。",
                None,
            )
        if operation == "绑定":
            return (
                "绑定由 QQ 网页确认流程处理，请发送 /MAA绑定 获取网页链接。"
            ), None
        if operation == "解绑":
            self.store.revoke(owner)
            return (
                "已解绑，旧密钥失效。已被 MAA 领取的任务不会因此停止；请在 MAA 本机确认。",
                None,
            )
        if operation in {"状态", "结果"}:
            binding, task = self.store.view(owner)
            if not binding:
                return "尚未绑定，请私聊 /MAA绑定。", None
            if not binding["device"]:
                state = (
                    "等待首次连接"
                    if self.store.clock() - binding["created"] <= 900
                    else "绑定密钥已过期，请重新 /MAA绑定"
                )
                return state, None
            seen = max(0, int(self.store.clock() - binding["seen"]))
            lines = [
                "【MAA 状态】",
                f"设备：{'在线' if seen <= 30 else '离线'}（{seen} 秒前联系）",
            ]
            image = None
            if task:
                states = {
                    "queued": "等待领取",
                    "dispatched": "已下发，等待回报",
                    "reported": "设备已回报",
                    "failed": "失败",
                    "expired": "过期取消",
                    "unknown": "结果未知",
                    "cancelled": "已取消",
                    "unconfirmed": "远程队列已空闲，原任务结果未确认",
                }
                lines += [f"最近指令：{task['type']}", f"状态：{states[task['state']]}"]
                if task["summary"]:
                    lines.append(task["summary"])
                if task["image"] and operation == "结果":
                    path = self.store.images / task["image"]
                    if path.is_file():
                        image = path
                with self.store.db() as db:
                    notice = db.execute(
                        "SELECT status,error,text FROM task_notice WHERE task_id=? "
                        "ORDER BY created DESC,rowid DESC LIMIT 1",
                        (task["id"],),
                    ).fetchone()
                if notice:
                    lines.append(notice["text"].splitlines()[0])
                if notice and notice["status"] == "failed":
                    lines.append(f"主动通知发送失败：{notice['error']}；结果可在这里查看。")
            return "\n".join(lines), image
        action = argument if operation == "开始" else operation
        if action not in {
            "一键长草",
            "唤醒",
            "基建",
            "刷理智",
            "公招",
            "信用",
            "领奖",
            "肉鸽",
            "截图",
            "停止",
            "心跳",
        }:
            return HELP, None
        task_id = self.store.enqueue(owner, action, origin=origin)
        return (
            (
                f"已提交“{action}”（{task_id[:8]}），等待 MAA 领取。\n"
                "收到回报后自动通知本会话；也可发送 /MAA结果 查询。未领取指令两分钟后失效。"
            ),
            None,
        )
