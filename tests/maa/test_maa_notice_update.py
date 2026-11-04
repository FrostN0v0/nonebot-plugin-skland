"""Exercise notice update SQL in memory, without files or QQ networking."""

import sqlite3
import unittest
from unittest.mock import Mock
from types import SimpleNamespace

import pytest
import bootstrap  # noqa: F401
from maa.notify import Notifications


class NoticeUpdateTests(unittest.TestCase):
    def setUp(self):
        self.database = sqlite3.connect(":memory:")
        self.addCleanup(self.database.close)
        self.database.row_factory = sqlite3.Row
        self.database.execute("""
            CREATE TABLE task_notice (
                task_id TEXT NOT NULL, version TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                text_sent INTEGER NOT NULL DEFAULT 0, image_sent INTEGER NOT NULL DEFAULT 0,
                lease REAL NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
                error TEXT NOT NULL DEFAULT '', PRIMARY KEY(task_id,version)
            )
        """)
        self.database.executemany(
            "INSERT INTO task_notice(task_id,version) VALUES(?,?)",
            [("task", "ended"), ("task", "offline"), ("other-task", "ended")],
        )
        self.database.commit()
        self.pump = Notifications(SimpleNamespace(db=lambda: self.database), Mock())
        self.notice = self.rows()[1]

    def rows(self):
        return [dict(row) for row in self.database.execute("SELECT * FROM task_notice ORDER BY task_id,version")]

    def test_rejects_unknown_fields_before_writing(self):
        before = self.rows()
        for fields in ({}, {"status": "sent", "error=? WHERE 1=1 --": "injected"}):
            with pytest.raises(ValueError, match="invalid delivery update"):
                self.pump.update(self.notice, **fields)
            assert self.rows() == before

    def test_binds_values_and_notice_identity(self):
        before = self.rows()
        payload = "'; DELETE FROM task_notice; --"
        self.pump.update({**self.notice, "task_id": "' OR 1=1 --"}, error=payload)
        self.pump.update({**self.notice, "version": "' OR 1=1 --"}, error=payload)
        assert self.rows() == before
        fields = {
            "status": "failed",
            "text_sent": 1,
            "image_sent": 1,
            "lease": 10,
            "next_attempt": 30,
            "error": payload,
        }
        self.pump.update(self.notice, **fields)
        assert self.rows() == [before[0], {**self.notice, **fields}, before[2]]
        self.pump.update(self.notice, error="")
        assert self.rows() == [before[0], {**self.notice, **fields, "error": ""}, before[2]]

    def test_rolls_back_all_fields_on_failure(self):
        before = self.rows()
        with pytest.raises(sqlite3.IntegrityError):
            self.pump.update(self.notice, status="failed", text_sent=None)
        assert self.rows() == before
