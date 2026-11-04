"""Bot-private pairing state. The public worker cannot open this database."""

import stat
import time
import uuid
import hashlib
import secrets
import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager


class BindingError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class BindingStore:
    def __init__(self, path, issue, public_url, clock=time.time):
        self.issue = issue
        self.public_url = public_url
        self.clock = clock
        self.lock = threading.RLock()
        if str(path) != ":memory:":
            Path(path).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), timeout=5, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            PRAGMA foreign_keys=ON;
            PRAGMA secure_delete=ON;
            CREATE TABLE IF NOT EXISTS entry (
                id TEXT PRIMARY KEY, bot TEXT NOT NULL, owner TEXT NOT NULL,
                target TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL,
                closed INTEGER NOT NULL DEFAULT 0, identity TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS candidate (
                id TEXT PRIMARY KEY, entry_id TEXT NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
                session_hash TEXT NOT NULL, device TEXT NOT NULL, code TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending', notice TEXT NOT NULL DEFAULT 'pending',
                UNIQUE(entry_id,session_hash)
            );
        """)
        if str(path) != ":memory:" and stat.S_IMODE(Path(path).stat().st_mode) != 0o600:
            Path(path).chmod(0o600)

    @contextmanager
    def db(self):
        with self.lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                yield self.connection
                self.connection.commit()
            except BaseException:
                self.connection.rollback()
                raise

    def create(self, bot, user, target, identity):
        now, owner = self.clock(), digest(user)
        with self.db() as db:
            db.execute("DELETE FROM entry WHERE expires<?", (now,))
            last = db.execute("SELECT MAX(created) FROM entry WHERE bot=? AND owner=?", (bot, owner)).fetchone()[0]
            if last is not None and now - last < 10:
                raise BindingError("请稍等十秒后再生成新的绑定链接。")
            if db.execute("SELECT COUNT(*) FROM entry").fetchone()[0] >= 100:
                raise BindingError("绑定申请暂时已满，请稍后再试。")
            db.execute(
                "UPDATE candidate SET state='superseded' WHERE state IN ('pending','approved') AND entry_id IN "
                "(SELECT id FROM entry WHERE bot=? AND owner=?)",
                (bot, owner),
            )
            db.execute("UPDATE entry SET closed=1 WHERE bot=? AND owner=?", (bot, owner))
            entry = secrets.token_urlsafe(24)
            db.execute(
                "INSERT INTO entry VALUES(?,?,?,?,?,?,0,?)", (entry, bot, owner, target, now, now + 600, identity)
            )
        return entry

    def _entry(self, db, entry):
        row = db.execute("SELECT * FROM entry WHERE id=?", (entry,)).fetchone()
        if not row or row["expires"] <= self.clock():
            raise BindingError("绑定链接已过期，请回原 QQ 会话重新发送 /MAA绑定。")
        return row

    def submit(self, entry, session, device):
        try:
            device = str(uuid.UUID(device.strip()))
        except (ValueError, AttributeError):
            raise BindingError("请填写 MAA 显示的完整设备 ID。") from None
        with self.db() as db:
            parent = self._entry(db, entry)
            previous = db.execute(
                "SELECT * FROM candidate WHERE entry_id=? AND session_hash=?", (entry, digest(session))
            ).fetchone()
            if previous:
                if previous["device"] != device:
                    raise BindingError("这份申请已提交，修改设备 ID 请重新发起绑定。")
                return dict(previous)
            if parent["closed"]:
                raise BindingError("这份绑定已经结束，请回原 QQ 会话重新发起。")
            if db.execute("SELECT COUNT(*) FROM candidate WHERE entry_id=?", (entry,)).fetchone()[0] >= 3:
                raise BindingError("这个链接的浏览器申请已满，请回原 QQ 会话重新生成链接。")
            candidate = secrets.token_hex(16)
            alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
            raw = "".join(secrets.choice(alphabet) for _ in range(6))
            code = raw[:4] + "-" + raw[4:]
            db.execute(
                "INSERT INTO candidate(id,entry_id,session_hash,device,code) VALUES(?,?,?,?,?)",
                (candidate, entry, digest(session), device, code),
            )
            return dict(db.execute("SELECT * FROM candidate WHERE id=?", (candidate,)).fetchone())

    def status(self, entry, session):
        with self.db() as db:
            parent = self._entry(db, entry)
            row = db.execute(
                "SELECT state,device,code,notice FROM candidate WHERE entry_id=? AND session_hash=?",
                (entry, digest(session)),
            ).fetchone()
            if not row:
                return {"state": "ended" if parent["closed"] else "not_submitted"}
            return dict(row)

    def decide(self, candidate, approve, bot, user, target):
        with self.db() as db:
            row = db.execute(
                "SELECT c.*,e.bot,e.owner,e.target,e.expires,e.closed FROM candidate c JOIN entry e ON e.id=c.entry_id "
                "WHERE c.id=?",
                (candidate,),
            ).fetchone()
            if (
                not row
                or row["expires"] <= self.clock()
                or row["closed"]
                or row["state"] != "pending"
                or (row["bot"], row["owner"], row["target"]) != (bot, digest(user), target)
            ):
                return False
            state = "approved" if approve else "cancelled"
            db.execute("UPDATE candidate SET state=? WHERE id=?", (state, candidate))
            db.execute(
                "UPDATE candidate SET state='superseded' WHERE entry_id=? AND id<>?", (row["entry_id"], candidate)
            )
            db.execute("UPDATE entry SET closed=1 WHERE id=?", (row["entry_id"],))
            return True

    def latest(self, bot, user, target):
        with self.db() as db:
            row = db.execute(
                "SELECT c.*,e.bot,e.target FROM candidate c JOIN entry e ON e.id=c.entry_id "
                "WHERE e.bot=? AND e.owner=? AND e.target=? AND e.expires>? AND e.closed=0 "
                "AND c.state='pending' ORDER BY c.rowid DESC LIMIT 1",
                (bot, digest(user), target, self.clock()),
            ).fetchone()
            return dict(row) if row else None

    def claim_notice(self, bots):
        with self.db() as db:
            rows = db.execute(
                "SELECT c.*,e.bot,e.target FROM candidate c JOIN entry e ON e.id=c.entry_id "
                "WHERE c.notice='pending' AND c.state='pending' AND e.closed=0 AND e.expires>? LIMIT 100",
                (self.clock(),),
            ).fetchall()
            for row in rows:
                if row["bot"] in bots:
                    db.execute("UPDATE candidate SET notice='sending' WHERE id=?", (row["id"],))
                    return dict(row)
        return None

    def notice_result(self, candidate, success):
        with self.db() as db:
            db.execute("UPDATE candidate SET notice=? WHERE id=?", ("sent" if success else "failed", candidate))

    def invalidate(self, identity):
        with self.db() as db:
            db.execute("DELETE FROM entry WHERE identity=?", (identity,))

    def cleanup(self):
        with self.db() as db:
            db.execute("DELETE FROM entry WHERE expires<=?", (self.clock(),))

    def redeem(self, entry, session):
        # The one-time plaintext key is returned only to the confirmed browser.
        # Never persist it in pairing state, messages, URLs or logs.
        with self.db() as db:
            parent = self._entry(db, entry)
            row = db.execute(
                "SELECT * FROM candidate WHERE entry_id=? AND session_hash=?",
                (entry, digest(session)),
            ).fetchone()
            if not row or row["state"] != "approved":
                raise BindingError("未获确认或连接设置已经领取；如领取失败，请重新 /MAA绑定。")
            try:
                scene, target = parent["target"].split(":", 1)
                key = self.issue(
                    parent["identity"],
                    row["device"],
                    origin={"bot_id": parent["bot"], "scene": scene, "target": target},
                )
            except ValueError as error:
                raise BindingError(str(error)) from None
            db.execute("UPDATE candidate SET state='delivered' WHERE id=?", (row["id"],))
            return {
                "key": key,
                "get_task": self.public_url + "/maa/getTask",
                "report_status": self.public_url + "/maa/reportStatus",
            }
