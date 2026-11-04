"""QQ owner confirmation and browser binding, shared by group and private handlers."""

import re
import asyncio

from nonebot.adapters.qq import MessageSegment
from nonebot.adapters.qq.models import MessageKeyboard

from .binding_rpc import serve
from .binding_state import BindingError, BindingStore


def target_for(event, private):
    return ("private:" + event.get_user_id()) if private else ("group:" + event.group_openid)


def confirmation(row):
    text = (
        f"MAA 绑定申请\n\n设备 ID：{row['device'][:4]}…{row['device'][-4:]}\n网页校验码：{row['code']}\n\n"
        "请与自己打开的网页核对一致后确认。仅命令发起者可以确认。"
    )
    buttons = [
        {
            "id": action,
            "render_data": {"label": label, "visited_label": label, "style": 1},
            "action": {"type": 1, "permission": {"type": 2}, "data": f"maabind:{row['id']}:{action}"},
        }
        for label, action in (("确认绑定", "ok"), ("取消", "cancel"))
    ]
    return MessageSegment.markdown(text) + MessageSegment.keyboard(
        MessageKeyboard(content={"rows": [{"buttons": buttons}]})
    )


class BindingFlow:
    def __init__(self, path, socket, store, public_url, log):
        self.store = BindingStore(path, store.issue, public_url)
        self.remote = store
        self.socket = socket
        self.public_url = public_url
        self.log = log
        self.origins = {}
        self.server = None

    async def command(self, send, bot, event, owner, private, argument):
        target = target_for(event, private)
        try:
            if argument.strip() == "查询":
                row = await asyncio.to_thread(self.store.latest, bot.self_id, event.get_user_id(), target)
                await send(confirmation(row) if row else "没有待确认的网页申请，请先在网页填写设备标识符。")
                return
            if argument.strip():
                await send("请发送 /MAA绑定，或发送 /MAA绑定 查询 取回确认按钮。")
                return
            binding, _ = await asyncio.to_thread(self.remote.view, owner)
            if binding and binding["device"]:
                await send("已绑定设备；更换设备请先发送 /MAA解绑。")
                return
            if self.server is None:
                await send("网页绑定服务尚未启动，请管理员完成绑定服务配置并重启 bot。")
                return
            entry = await asyncio.to_thread(self.store.create, bot.self_id, event.get_user_id(), target, owner)
            self.origins[entry] = {
                "msg_id": getattr(event, "id", None),
                "event_id": getattr(event, "event_id", None),
                "seq": 1,
            }
            await send(
                f"MAA 绑定\n请用最终接收连接设置的浏览器打开：\n{self.public_url}/maa/bind?request={entry}\n"
                "设备标识符位置：MAA设置-远程控制-设备标识符\n填写后返回本会话核对网页校验码并确认。"
                "链接十分钟有效；未出现确认消息时发送 /MAA绑定 查询。"
            )
        except BindingError as error:
            await send(str(error))

    async def click(self, bot, event):
        match = re.fullmatch(r"maabind:([a-f0-9]{32}):(ok|cancel)", event.data.resolved.button_data or "")
        valid = bool(match and event.chat_type in (1, 2))
        if valid:
            valid = await asyncio.to_thread(
                self.store.decide,
                match[1],
                match[2] == "ok",
                bot.self_id,
                event.get_user_id(),
                target_for(event, event.chat_type == 2),
            )
        await bot.put_interaction(interaction_id=event.id, code=0 if valid else 1)
        if valid:
            kwargs = {
                "event_id": event.event_id,
                "msg_seq": 1,
                "message": "绑定申请已确认，请回原浏览器领取连接设置。" if match[2] == "ok" else "绑定申请已取消。",
            }
            if event.chat_type == 2:
                await bot.send_to_c2c(openid=event.user_openid, **kwargs)
            else:
                await bot.send_to_group(group_openid=event.group_openid, **kwargs)

    async def tick(self, bots):
        await asyncio.to_thread(self.store.cleanup)
        row = await asyncio.to_thread(self.store.claim_notice, set(bots))
        if row:
            success = False
            try:
                origin = self.origins.get(row["entry_id"])
                if origin:
                    origin["seq"] += 1
                    scene, target = row["target"].split(":", 1)
                    kwargs = {"message": confirmation(row), "msg_seq": origin["seq"]}
                    if origin["event_id"]:
                        kwargs["event_id"] = origin["event_id"]
                    else:
                        kwargs["msg_id"] = origin["msg_id"]
                    if scene == "private":
                        await bots[row["bot"]].send_to_c2c(openid=target, **kwargs)
                    else:
                        await bots[row["bot"]].send_to_group(group_openid=target, **kwargs)
                    success = True
            except Exception as error:  # noqa: BLE001 -- Don't log platform payloads.
                self.log.warning(f"MAA binding notice failure type={type(error).__name__}")
            await asyncio.to_thread(self.store.notice_result, row["id"], success)
        connected = await asyncio.to_thread(self.remote.claim_connection_notice, set(bots))
        if connected:
            success = False
            try:
                message = "MAA 首次连接成功，设备已绑定。发送 /MAA状态 查看状态，或 /maa 使用菜单。"
                if connected["scene"] == "private":
                    await bots[connected["bot_id"]].send_to_c2c(openid=connected["target"], message=message)
                else:
                    await bots[connected["bot_id"]].send_to_group(group_openid=connected["target"], message=message)
                success = True
            except Exception as error:  # noqa: BLE001 -- Never log platform payloads.
                self.log.warning(f"MAA connection notice failure type={type(error).__name__}")
            await asyncio.to_thread(self.remote.connection_notice_result, connected["binding_id"], success)
        with self.store.db() as db:
            alive = {row[0] for row in db.execute("SELECT id FROM entry")}
        self.origins = {k: v for k, v in self.origins.items() if k in alive}

    async def start(self):
        if self.socket:
            self.server = await serve(self.store, self.socket)

    async def close(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.store.connection.close()
