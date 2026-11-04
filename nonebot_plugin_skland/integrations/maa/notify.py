"""Durable QQ result delivery. The public gateway never receives QQ credentials."""

# ruff: noqa: BLE001 -- Never log raw QQ responses, target IDs or credentials.

import uuid
import asyncio

from nonebot.adapters.qq import MessageSegment

from .core import RETENTION, TASK_TYPES

NAMES = {value: key for key, value in TASK_TYPES.items()}


def error_summary(error):
    code = getattr(error, "code", None)
    reasons = {
        40034105: "主动消息权限未开启",
        40034100: "QQ 消息频控",
        40054002: "机器人被禁言",
        40034101: "机器人已不在群内",
        40034004: "图片转存失败",
    }
    if isinstance(code, int):
        return f"QQ {code}：{reasons.get(code, '发送失败')}"
    return type(error).__name__


def stop_outcome(row, now):
    if row["check_state"] == "reported" and row["check_summary"] == "当前无远程任务执行":
        return "stopped"
    if now - row["updated"] < 90 and row["check_count"] < 3:
        return "checking"
    # The third probe must finish before interpreting its result.
    if now - row["updated"] < 90 and row["check_state"] in {"queued", "dispatched"}:
        return "checking"
    return "stop_unconfirmed"


def outcome(row, stops, now):
    """State from available evidence; SUCCESS has no native end-reason field."""
    state, kind = row["state"], row["type"]
    if state == "queued":
        return None
    if state == "dispatched":
        if now - row["seen"] > 60 and now - row["updated"] > 60:
            return "offline", "设备连接中断", "执行结果未知，不能判断是否已终止。"
        return None
    if state == "failed":
        return "failed", "执行失败", row["summary"]
    if state == "expired":
        return "expired", "过期取消", "设备未在两分钟内领取指令。"
    if state == "cancelled":
        return "cancelled", "已取消", "指令尚未下发，已被停止操作取消。"
    if state == "unknown":
        return (
            "unknown",
            "等待回报超时",
            "实际结果未知，不能据此判断正常完成或异常终止。",
        )
    if state == "unconfirmed":
        stop = stops.get(row["stop_id"])
        if stop and stop["state"] == "reported" and stop_outcome(stop, now) == "stopped":
            return "stopped", "已停止", "停止指令已回报，心跳确认远程任务队列空闲。"
        return "unconfirmed", "远程队列已空闲", "原任务回报缺失，结束原因无法确认。"
    if state != "reported":
        return None
    if kind == "StopTask":
        result = stop_outcome(row, now)
        if result == "checking":
            return None
        if result == "stopped":
            return result, "已停止", "停止指令已回报，心跳确认远程任务队列空闲。"
        return (
            result,
            "停止尚未确认",
            "已收到停止指令回报，但未确认远程队列空闲；请检查截图或本机。",
        )
    if kind.startswith("LinkStart"):
        stop = stops.get(row["stop_id"])
        if stop and stop["state"] == "reported":
            result = stop_outcome(stop, now)
            if result == "checking":
                return None
            if result == "stopped":
                return result, "已停止", "期间收到 bot 停止请求，现已确认远程队列空闲。"
            return (
                "ended_stop_requested",
                "执行已结束",
                "期间有停止请求；具体结束原因未由 MAA 提供。",
            )
        return (
            "ended",
            "执行已结束",
            "MAA 回报 SUCCESS；未提供正常完成、本机停止或异常结束的具体原因。",
        )
    return (
        "reported",
        "截图已取得" if kind == "CaptureImageNow" else "指令已回报",
        row["summary"],
    )


class Notifications:
    def __init__(self, store, log):
        self.store = store
        self.log = log
        self.lock = asyncio.Lock()
        self.next_send = 0.0

    def collect(self):
        now = self.store.clock()
        with self.store.db() as db:
            self.store.expire(db)
            rows = db.execute(
                "SELECT t.*,o.bot_id,o.scene,o.target,o.stop_id,o.check_id,o.check_count,"
                "o.check_after,b.seen,c.state AS check_state,c.summary AS check_summary "
                "FROM task t JOIN task_origin o ON o.task_id=t.id "
                "JOIN binding b ON b.id=t.binding_id LEFT JOIN task c ON c.id=o.check_id "
                "WHERE o.scene IN ('group','private') AND t.created>=?",
                (now - RETENTION,),
            ).fetchall()
            rows = [dict(row) for row in rows]
            stops = {row["id"]: row for row in rows if row["type"] == "StopTask"}
            for row in stops.values():
                if (
                    row["state"] != "reported"
                    or stop_outcome(row, now) != "checking"
                    or row["check_count"] >= 3
                    or now < max(row["updated"] + 5, row["check_after"])
                    or row["check_state"] in {"queued", "dispatched"}
                ):
                    continue
                probe = uuid.uuid4().hex
                db.execute(
                    "INSERT INTO task(id,binding_id,type,state,created,updated) VALUES(?,?,'HeartBeat','queued',?,?)",
                    (probe, row["binding_id"], now, now),
                )
                # Internal verification never creates a standalone QQ notification
                # or obscures the user's most recent command in /MAA结果.
                db.execute(
                    "INSERT INTO task_origin(task_id,bot_id,scene,target) VALUES(?,?,'internal',?)",
                    (probe, row["bot_id"], row["target"]),
                )
                db.execute(
                    "UPDATE task_origin SET check_id=?,check_count=check_count+1,check_after=? WHERE task_id=?",
                    (probe, now + 10, row["id"]),
                )
                self.store.audit(db, row["binding_id"], "HeartBeat", "stop_verification")
            for row in rows:
                result = outcome(row, stops, now)
                if not result:
                    continue
                version, title, detail = result
                text = f"【MAA · {title}】\n任务：{NAMES.get(row['type'], row['type'])}（{row['id'][:8]}）\n{detail}"
                db.execute(
                    "INSERT OR IGNORE INTO task_notice(task_id,version,text,image,created) VALUES(?,?,?,?,?)",
                    (row["id"], version, text, row["image"], now),
                )
            # A late definitive report supersedes an unsent timeout/offline notice.
            db.execute(
                "UPDATE task_notice SET status='superseded' WHERE status='pending' "
                "AND version IN ('offline','unknown','unconfirmed') AND task_id IN "
                "(SELECT id FROM task WHERE state IN ('reported','failed'))"
            )

    def claim(self, bot_ids):
        now = self.store.clock()
        with self.store.db() as db:
            db.execute(
                "UPDATE task_notice SET status='failed',error='发送中断，送达状态未知' "
                "WHERE status='pending' AND attempts>=3 AND lease<=?",
                (now,),
            )
            rows = db.execute(
                "SELECT n.*,o.bot_id,o.scene,o.target FROM task_notice n "
                "JOIN task_origin o ON o.task_id=n.task_id "
                "WHERE n.status='pending' AND n.attempts<3 AND n.next_attempt<=? "
                "AND n.lease<=? ORDER BY n.created,n.rowid LIMIT 100",
                (now, now),
            ).fetchall()
            for row in rows:
                if row["bot_id"] in bot_ids:
                    db.execute(
                        "UPDATE task_notice SET lease=?,attempts=attempts+1 WHERE task_id=? AND version=?",
                        (now + 90, row["task_id"], row["version"]),
                    )
                    return dict(row)
        return None

    def update(self, notice, **fields):
        allowed = {
            "status",
            "text_sent",
            "image_sent",
            "lease",
            "next_attempt",
            "error",
        }
        if not fields or not fields.keys() <= allowed:
            raise ValueError("invalid delivery update")
        with self.store.db() as db:
            db.execute(
                "UPDATE task_notice SET " + ",".join(f"{key}=?" for key in fields) + " WHERE task_id=? AND version=?",
                (*fields.values(), notice["task_id"], notice["version"]),
            )

    async def send(self, bot, notice, message):
        async with self.lock:
            loop = asyncio.get_running_loop()
            await asyncio.sleep(max(0, self.next_send - loop.time()))
            try:
                if notice["scene"] == "group":
                    await bot.send_to_group(group_openid=notice["target"], message=message)
                else:
                    await bot.send_to_c2c(openid=notice["target"], message=message)
            finally:
                self.next_send = loop.time() + 2.1

    async def tick(self, bots):
        await asyncio.to_thread(self.collect)
        # Bound each cycle; disconnected bots leave pending messages untouched.
        for _ in range(10):
            notice = await asyncio.to_thread(self.claim, set(bots))
            if not notice:
                return
            try:
                bot = bots[notice["bot_id"]]
                if not notice["text_sent"]:
                    await asyncio.wait_for(self.send(bot, notice, notice["text"]), 30)
                    await asyncio.to_thread(self.update, notice, text_sent=1)
                if notice["image"] and not notice["image_sent"]:
                    image = self.store.images / notice["image"]
                    if image.is_file():
                        await asyncio.wait_for(self.send(bot, notice, MessageSegment.file_image(image)), 30)
                    else:
                        await asyncio.wait_for(
                            self.send(bot, notice, "截图已清理或不可用，请重新获取截图。"),
                            30,
                        )
                    await asyncio.to_thread(self.update, notice, image_sent=1)
                await asyncio.to_thread(self.update, notice, status="sent", lease=0, error="")
                self.log.info(f"MAA result delivered task={notice['task_id'][:8]} state={notice['version']}")
            except Exception as error:
                reason = error_summary(error)
                final = notice["attempts"] >= 2
                await asyncio.to_thread(
                    self.update,
                    notice,
                    status="failed" if final else "pending",
                    lease=0,
                    next_attempt=self.store.clock() + (120 if notice["attempts"] else 30),
                    error=reason,
                )
                self.log.error(
                    f"MAA result delivery failure task={notice['task_id'][:8]} reason={reason} retry={not final}"
                )
