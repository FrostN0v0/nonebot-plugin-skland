"""MAA remote protocol state. No QQ credentials or game account data are stored."""

import io
import stat
import time
import uuid
import base64
import hashlib
import secrets
import sqlite3
from pathlib import Path
from contextlib import contextmanager

from PIL import Image

RETENTION = 3 * 86400
TASK_TYPES = {
    "一键长草": "LinkStart",
    "唤醒": "LinkStart-WakeUp",
    "基建": "LinkStart-Base",
    "刷理智": "LinkStart-Combat",
    "公招": "LinkStart-Recruiting",
    "信用": "LinkStart-Mall",
    "领奖": "LinkStart-Mission",
    "肉鸽": "LinkStart-AutoRoguelike",
    "截图": "CaptureImageNow",
    "停止": "StopTask",
    "心跳": "HeartBeat",
}


class RemoteError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def device_matches(expected, actual):
    # MAA may emit Guid "N" (32 hex) or "D" (hyphenated) format.
    try:
        return secrets.compare_digest(uuid.UUID(expected).bytes, uuid.UUID(actual).bytes)
    except ValueError:
        return secrets.compare_digest(expected, actual)


class Store:
    def __init__(self, directory, clock=time.time):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.images = self.directory / "images"
        self.images.mkdir(exist_ok=True)
        self.path = self.directory / "maa.sqlite3"
        self.clock = clock
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS binding (
                    id TEXT PRIMARY KEY, owner TEXT UNIQUE NOT NULL,
                    key_hash TEXT UNIQUE NOT NULL, device TEXT,
                    created REAL NOT NULL, seen REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS task (
                    id TEXT PRIMARY KEY, binding_id TEXT NOT NULL
                        REFERENCES binding(id) ON DELETE CASCADE,
                    type TEXT NOT NULL, state TEXT NOT NULL,
                    created REAL NOT NULL, updated REAL NOT NULL,
                    summary TEXT NOT NULL DEFAULT '', image TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS audit (
                    at REAL NOT NULL, binding_id TEXT NOT NULL,
                    action TEXT NOT NULL, outcome TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS received_message (
                    id TEXT PRIMARY KEY, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_origin (
                    task_id TEXT PRIMARY KEY REFERENCES task(id) ON DELETE CASCADE,
                    bot_id TEXT NOT NULL, scene TEXT NOT NULL, target TEXT NOT NULL,
                    stop_id TEXT NOT NULL DEFAULT '',
                    check_id TEXT NOT NULL DEFAULT '',
                    check_count INTEGER NOT NULL DEFAULT 0,
                    check_after REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS task_notice (
                    task_id TEXT NOT NULL REFERENCES task(id) ON DELETE CASCADE,
                    version TEXT NOT NULL, text TEXT NOT NULL, image TEXT NOT NULL,
                    created REAL NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                    text_sent INTEGER NOT NULL DEFAULT 0,
                    image_sent INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt REAL NOT NULL DEFAULT 0,
                    lease REAL NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY(task_id,version)
                );
                CREATE TABLE IF NOT EXISTS binding_origin (
                    binding_id TEXT PRIMARY KEY REFERENCES binding(id) ON DELETE CASCADE,
                    bot_id TEXT NOT NULL, scene TEXT NOT NULL, target TEXT NOT NULL,
                    notice TEXT NOT NULL DEFAULT 'pending'
                );
            """)
            if "expected_device" not in {row[1] for row in db.execute("PRAGMA table_info(binding)")}:
                db.execute("ALTER TABLE binding ADD COLUMN expected_device TEXT")
        # Both services share the group, but only the file owner can chmod it.
        if stat.S_IMODE(self.path.stat().st_mode) != 0o660:
            self.path.chmod(0o660)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA secure_delete=ON")
        try:
            # Serialize claim/poll/report and avoid concurrent double dispatch.
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def audit(self, db, binding_id, action, outcome):
        db.execute(
            "INSERT INTO audit VALUES(?,?,?,?)",
            (self.clock(), binding_id, action, outcome),
        )

    def claim_message(self, owner, message_id):
        with self.db() as db:
            result = db.execute(
                "INSERT OR IGNORE INTO received_message VALUES(?,?)",
                (digest(owner + ":" + message_id), self.clock()),
            )
            return result.rowcount == 1

    def issue(self, owner, expected_device=None, origin=None):
        now = self.clock()
        key = "maa_" + secrets.token_urlsafe(32)
        with self.db() as db:
            old = db.execute("SELECT * FROM binding WHERE owner=?", (owner,)).fetchone()
            if old and old["device"]:
                raise RemoteError("已绑定设备；如需更换，请先 /MAA解绑。")
            if not old and db.execute("SELECT COUNT(*) FROM binding").fetchone()[0] >= 20:
                raise RemoteError("当前设备绑定名额已满，请联系管理员。")
            if old:
                db.execute("DELETE FROM binding WHERE id=?", (old["id"],))
            binding_id = uuid.uuid4().hex
            db.execute(
                "INSERT INTO binding(id,owner,key_hash,created,expected_device) VALUES(?,?,?,?,?)",
                (binding_id, owner, digest(key), now, expected_device),
            )
            self.audit(db, binding_id, "bind", "pending")
            if origin:
                db.execute(
                    "INSERT INTO binding_origin(binding_id,bot_id,scene,target) VALUES(?,?,?,?)",
                    (binding_id, origin["bot_id"], origin["scene"], origin["target"]),
                )
        return key

    def claim_connection_notice(self, bots):
        with self.db() as db:
            rows = db.execute(
                "SELECT o.* FROM binding_origin o JOIN binding b ON b.id=o.binding_id "
                "WHERE b.device IS NOT NULL AND o.notice='pending'"
            ).fetchall()
            for row in rows:
                if row["bot_id"] in bots:
                    db.execute("UPDATE binding_origin SET notice='sending' WHERE binding_id=?", (row["binding_id"],))
                    return dict(row)
        return None

    def connection_notice_result(self, binding_id, success):
        with self.db() as db:
            db.execute(
                "UPDATE binding_origin SET notice=? WHERE binding_id=?",
                ("sent" if success else "failed", binding_id),
            )

    def revoke(self, owner):
        with self.db() as db:
            row = db.execute("SELECT id FROM binding WHERE owner=?", (owner,)).fetchone()
            if row:
                self.audit(db, row["id"], "unbind", "revoked")
                # Delete device images immediately, not just their DB references.
                for task in db.execute("SELECT image FROM task WHERE binding_id=?", (row["id"],)):
                    if task["image"]:
                        (self.images / task["image"]).unlink(missing_ok=True)
                db.execute("DELETE FROM binding WHERE owner=?", (owner,))

    def authenticate(self, db, key, device, claim=False):
        if not isinstance(key, str) or not key.isascii() or not 40 <= len(key) <= 100:
            raise RemoteError("authentication")
        if not isinstance(device, str) or not device.isascii() or not 1 <= len(device) <= 128:
            raise RemoteError("authentication")
        row = db.execute("SELECT * FROM binding WHERE key_hash=?", (digest(key),)).fetchone()
        if not row:
            raise RemoteError("authentication")
        if row["device"] is None:
            if not claim or self.clock() - row["created"] > 900:
                raise RemoteError("authentication")
            if row["expected_device"] and not device_matches(row["expected_device"], device):
                raise RemoteError("authentication")
            db.execute("UPDATE binding SET device=? WHERE id=?", (device, row["id"]))
            self.audit(db, row["id"], "bind", "connected")
        elif not device_matches(row["device"], device):
            raise RemoteError("authentication")
        return row

    def poll(self, key, device):
        now = self.clock()
        with self.db() as db:
            row = self.authenticate(db, key, device, claim=True)
            db.execute("UPDATE binding SET seen=? WHERE id=?", (now, row["id"]))
            self.expire(db)
            task = db.execute(
                "SELECT * FROM task WHERE binding_id=? AND state='queued' ORDER BY created,rowid LIMIT 1",
                (row["id"],),
            ).fetchone()
            if not task:
                return {"tasks": []}
            db.execute(
                "UPDATE task SET state='dispatched',updated=? WHERE id=?",
                (now, task["id"]),
            )
            self.audit(db, row["id"], task["type"], "dispatched")
            # At-most-once dispatch: a lost HTTP response becomes unknown, never auto-runs again.
            return {"tasks": [{"id": task["id"], "type": task["type"]}]}

    def expire(self, db):
        now = self.clock()
        db.execute(
            "UPDATE task SET state='expired',summary='设备未及时领取，已取消',updated=? "
            "WHERE state='queued' AND created<?",
            (now, now - 120),
        )
        db.execute(
            "UPDATE task SET state='unknown',summary='超时未回报，实际结果未知',updated=? "
            "WHERE state='dispatched' AND updated<?",
            (now, now - 3600),
        )

    def enqueue(self, owner, name, origin=None):
        if name not in TASK_TYPES:
            raise RemoteError("支持：" + "、".join(TASK_TYPES))
        if origin is not None and (
            origin.get("scene") not in {"group", "private"}
            or not all(isinstance(origin.get(key), str) and 0 < len(origin[key]) <= 128 for key in ("bot_id", "target"))
        ):
            raise RemoteError("无法确定任务结果通知的会话，未提交任务。")
        now = self.clock()
        task_id = uuid.uuid4().hex
        with self.db() as db:
            row = db.execute("SELECT * FROM binding WHERE owner=?", (owner,)).fetchone()
            if not row or not row["device"]:
                raise RemoteError("尚未连接设备，请先 /MAA绑定。")
            if now - row["seen"] > 30:
                raise RemoteError("MAA 当前离线，未下发任务。请确认 MAA 与远控已开启。")
            self.expire(db)
            if TASK_TYPES[name].startswith("LinkStart"):
                active = db.execute(
                    "SELECT 1 FROM task WHERE binding_id=? AND type LIKE 'LinkStart%' "
                    "AND state IN ('queued','dispatched','unknown') LIMIT 1",
                    (row["id"],),
                ).fetchone()
                if active:
                    raise RemoteError(
                        "已有执行任务或结果待确认；请先查看 /MAA结果，必要时停止并用 /MAA 心跳 确认空闲。"
                    )
            if name == "停止":
                db.execute(
                    "UPDATE task SET state='cancelled',summary='停止时取消待领取任务',updated=? "
                    "WHERE binding_id=? AND state='queued'",
                    (now, row["id"]),
                )
                db.execute(
                    "UPDATE task_origin SET stop_id=? WHERE task_id IN "
                    "(SELECT id FROM task WHERE binding_id=? AND type LIKE 'LinkStart%' "
                    "AND state IN ('dispatched','unknown'))",
                    (task_id, row["id"]),
                )
            pending = db.execute(
                "SELECT COUNT(*) FROM task WHERE binding_id=? AND state='queued'",
                (row["id"],),
            ).fetchone()[0]
            if pending >= 5:
                raise RemoteError("待领取任务过多，请稍后再试。")
            db.execute(
                "INSERT INTO task(id,binding_id,type,state,created,updated) VALUES(?,?,?,'queued',?,?)",
                (task_id, row["id"], TASK_TYPES[name], now, now),
            )
            if origin is not None:
                db.execute(
                    "INSERT INTO task_origin(task_id,bot_id,scene,target) VALUES(?,?,?,?)",
                    (task_id, origin["bot_id"], origin["scene"], origin["target"]),
                )
            self.audit(db, row["id"], TASK_TYPES[name], "queued")
        return task_id

    def report(self, key, device, task_id, status, payload):
        if (
            not isinstance(status, str)
            or status not in {"SUCCESS", "FAILED"}
            or not isinstance(payload, str)
            or not isinstance(task_id, str)
        ):
            raise RemoteError("invalid_report")
        with self.db() as db:
            row = self.authenticate(db, key, device)
            task = db.execute("SELECT * FROM task WHERE id=? AND binding_id=?", (task_id, row["id"])).fetchone()
            if not task or task["state"] not in {
                "dispatched",
                "unknown",
                "reported",
                "failed",
                "unconfirmed",
            }:
                raise RemoteError("invalid_task")
            if task["state"] in {"reported", "failed"}:
                return  # Idempotent duplicate callback.
            image = ""
            summary = "设备已回报；不代表游戏任务实际成功"
            if status == "FAILED":
                summary = "设备报告失败，可查看 MAA 本地日志"
            elif task["type"] == "CaptureImageNow":
                try:
                    image = self.save_image(task["id"], payload)
                    summary = "已取得模拟器截图"
                except (ValueError, OSError, Image.DecompressionBombError):
                    status, summary = "FAILED", "截图无效或过大，未保存"
            elif task["type"] == "HeartBeat":
                summary = "当前有远程任务执行中" if payload else "当前无远程任务执行"
                if not payload:
                    db.execute(
                        "UPDATE task SET state='unconfirmed',"
                        "summary='心跳显示远程队列空闲，原任务结果未确认',updated=? "
                        "WHERE binding_id=? AND type LIKE 'LinkStart%' AND state IN ('dispatched','unknown')",
                        (self.clock(), row["id"]),
                    )
            elif task["type"] == "StopTask":
                summary = "已请求停止；请查询状态或截图确认"
            db.execute(
                "UPDATE task SET state=?,summary=?,image=?,updated=? WHERE id=?",
                (
                    "failed" if status == "FAILED" else "reported",
                    summary,
                    image,
                    self.clock(),
                    task_id,
                ),
            )
            self.audit(
                db,
                row["id"],
                task["type"],
                "failed" if status == "FAILED" else "reported",
            )

    def authorize_report(self, key, device, task_id, status):
        """Authenticate a small header before accepting screenshot payload bytes."""
        if not isinstance(task_id, str) or len(task_id) != 32 or status not in ("SUCCESS", "FAILED"):
            raise RemoteError("invalid report")
        with self.db() as db:
            row = self.authenticate(db, key, device)
            task = db.execute(
                "SELECT state FROM task WHERE id=? AND binding_id=?",
                (task_id, row["id"]),
            ).fetchone()
            if not task or task["state"] not in {
                "dispatched",
                "unknown",
                "unconfirmed",
                "reported",
                "failed",
            }:
                raise RemoteError("invalid report")

    def save_image(self, task_id, payload):
        if len(payload) > 11 * 1024 * 1024:
            raise ValueError("oversize")
        content = base64.b64decode(payload, validate=True)
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > 12_000_000 or image.format not in {
                "PNG",
                "JPEG",
            }:
                raise ValueError("invalid image")
            image.thumbnail((1920, 1920))
            path = self.images / (task_id + ".jpg")
            temporary = path.with_suffix(".tmp")
            try:
                image.convert("RGB").save(temporary, "JPEG", quality=85)
                temporary.chmod(0o660)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        return path.name

    def view(self, owner):
        with self.db() as db:
            self.expire(db)
            row = db.execute("SELECT * FROM binding WHERE owner=?", (owner,)).fetchone()
            if not row:
                return None, None
            task = db.execute(
                "SELECT * FROM task WHERE binding_id=? AND NOT EXISTS "
                "(SELECT 1 FROM task_origin o WHERE o.task_id=task.id AND o.scene='internal') "
                "ORDER BY created DESC,rowid DESC LIMIT 1",
                (row["id"],),
            ).fetchone()
            return dict(row), dict(task) if task else None

    def cleanup(self):
        before = self.clock() - RETENTION
        with self.db() as db:
            db.execute("DELETE FROM task WHERE created<?", (before,))
            db.execute("DELETE FROM audit WHERE at<?", (before,))
            db.execute("DELETE FROM received_message WHERE created<?", (before,))
            db.execute(
                "DELETE FROM binding WHERE device IS NULL AND created<?",
                (self.clock() - 900,),
            )
            self.expire(db)
        for pattern in ("*.jpg", "*.tmp"):
            for path in self.images.glob(pattern):
                try:
                    if path.stat().st_mtime < before:
                        path.unlink(missing_ok=True)
                except FileNotFoundError:
                    pass  # The other worker may have removed it concurrently.
