"""Scoped callback menus; no synthetic @bot command messages."""

import time
import secrets
from dataclasses import dataclass

from nonebot.adapters.qq import MessageSegment
from nonebot.adapters.qq.models import MessageKeyboard

PAGES = {
    "主页": (
        "MAA 远程控制",
        [
            ("绑定设备", "/MAA绑定"),
            ("状态与截图", "/maa 查看"),
            ("执行任务", "/maa 任务"),
            ("立即停止", "/MAA停止"),
            ("使用说明", "/maa 说明"),
        ],
    ),
    "查看": (
        "状态与截图",
        [
            ("在线状态", "/MAA状态"),
            ("获取截图", "/MAA截图"),
            ("最近结果 / 截图", "/MAA结果"),
            ("任务心跳", "/maa 心跳"),
            ("返回主页", "/maa"),
        ],
    ),
    "任务": (
        "执行任务 · 沿用 MAA 本机配置",
        [
            ("一键长草", "/maa 开始 一键长草"),
            ("刷理智", "/maa 开始 刷理智"),
            ("基建 / 公招", "/maa 基建公招"),
            ("其他任务", "/maa 其他任务"),
            ("返回主页", "/maa"),
        ],
    ),
    "基建公招": (
        "基建与公招",
        [
            ("基建换班", "/maa 开始 基建"),
            ("自动公招", "/maa 开始 公招"),
            ("返回任务", "/maa 任务"),
        ],
    ),
    "其他任务": (
        "其他任务",
        [
            ("唤醒游戏", "/maa 开始 唤醒"),
            ("信用购物", "/maa 开始 信用"),
            ("领取奖励", "/maa 开始 领奖"),
            ("自动肉鸽", "/maa 开始 肉鸽"),
            ("返回任务", "/maa 任务"),
        ],
    ),
    "说明": ("操作说明 · 私聊和群聊均可使用", [("返回主页", "/maa")]),
    "绑定说明": ("绑定设备 · 网页申请后由本人确认", [("绑定设备", "/MAA绑定"), ("返回主页", "/maa")]),
}


def page_for(name, private):
    if name == "管理":
        name = "主页"
    if name not in PAGES:
        return None
    title, options = PAGES[name]
    if name == "主页" and private:
        options = [
            ("绑定设备", "/MAA绑定"),
            ("状态与截图", "/maa 查看"),
            ("执行任务", "/maa 任务"),
            ("解绑设备", "/MAA解绑"),
            ("使用说明", "/maa 说明"),
        ]
    if name == "说明":
        title += "\n发送 /MAA绑定，网页填写设备标识符后回 QQ 确认。私聊或群聊均可操作，结果发送到发起会话。"
    if name == "绑定说明":
        title += "\n设备标识符位置：MAA设置-远程控制-设备标识符。核对网页校验码后确认，回原浏览器领取连接设置。"
    return title, options


@dataclass
class Menu:
    bot_id: str
    user_id: str
    session_id: str
    private: bool
    owner: str
    commands: tuple[str, ...]
    deadline: float
    claimed: bool = False


class Menus:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.items = {}

    def create(self, bot_id, user_id, session_id, private, owner, options):
        self.items = {k: v for k, v in self.items.items() if v.deadline > self.clock()}
        while len(self.items) >= 200:
            self.items.pop(next(iter(self.items)))
        nonce = secrets.token_urlsafe(12)
        self.items[nonce] = Menu(
            bot_id,
            user_id,
            session_id,
            private,
            owner,
            tuple(c for _, c in options),
            self.clock() + 600,
        )
        return nonce

    def claim(self, data, bot_id, user_id, session_id):
        parts = data.split(":")
        if len(parts) != 3 or parts[0] != "maamenu" or not parts[2].isascii() or not parts[2].isdigit():
            return None
        menu = self.items.get(parts[1])
        index = int(parts[2]) if len(parts[2]) <= 2 else 100
        if (
            menu is None
            or menu.claimed
            or menu.deadline <= self.clock()
            or (menu.bot_id, menu.user_id, menu.session_id) != (bot_id, user_id, session_id)
            or index >= len(menu.commands)
        ):
            return None
        menu.claimed = True
        return menu, menu.commands[index]


def keyboard_message(title, options, nonce):
    rows = []
    for i, (label, command) in enumerate(options):
        rows.append(
            {
                "buttons": [
                    {
                        "id": f"maa_{i}",
                        "render_data": {
                            "label": label,
                            "visited_label": label,
                            "style": 1,
                        },
                        "action": {
                            "type": 1,
                            "permission": {"type": 2},
                            "data": f"maamenu:{nonce}:{i}",
                        },
                    }
                ]
            }
        )
    return MessageSegment.markdown(title) + MessageSegment.keyboard(MessageKeyboard(content={"rows": rows}))
