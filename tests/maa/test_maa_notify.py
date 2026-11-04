import bootstrap  # noqa: F401

"""Local report -> durable outbox -> QQ delivery checks; no network or game."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock

from test_maa_remote import Fixture
from maa.notify import Notifications
from maa.core import RETENTION, Store


class NotificationTests(Fixture, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.connect()
        self.origin = {"bot_id": "bot", "scene": "group", "target": "alice-group"}
        self.bot = SimpleNamespace(send_to_group=AsyncMock(), send_to_c2c=AsyncMock())
        self.log = Mock()
        self.pump = Notifications(self.store, self.log)

    def submit(self, name="基建", origin=None):
        task = self.store.enqueue(self.owner, name, origin=origin or self.origin)
        self.connect()
        return task

    async def tick(self):
        self.pump.next_send = 0
        await self.pump.tick({"bot": self.bot})

    def notices(self, task):
        with self.store.db() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM task_notice WHERE task_id=? ORDER BY created,rowid",
                    (task,),
                )
            ]

    async def test_screenshot_is_delivered_automatically_once_to_origin_group(self):
        task = self.submit("截图")
        self.store.report(self.key, self.device, task, "SUCCESS", self.screenshot_payload())
        await self.tick()
        assert self.bot.send_to_group.await_count == 2
        calls = self.bot.send_to_group.call_args_list
        assert calls[0].kwargs["group_openid"] == "alice-group"
        assert "截图已取得" in calls[0].kwargs["message"]
        assert calls[1].kwargs["message"].type == "file_image"
        self.bot.send_to_c2c.assert_not_awaited()
        self.store.report(self.key, self.device, task, "SUCCESS", self.screenshot_payload())
        self.pump = Notifications(Store(self.temp.name, lambda: self.now), self.log)
        await self.tick()
        assert self.bot.send_to_group.await_count == 2
        assert self.notices(task)[0]["status"] == "sent"

    async def test_native_success_is_end_reason_unknown_and_failed_is_explicit(self):
        task = self.submit()
        self.store.report(self.key, self.device, task, "SUCCESS", "")
        await self.tick()
        text = self.bot.send_to_group.call_args.kwargs["message"]
        assert "执行已结束" in text
        assert "未提供正常完成、本机停止或异常结束" in text
        task = self.submit()
        self.store.report(self.key, self.device, task, "FAILED", "")
        await self.tick()
        assert "执行失败" in self.bot.send_to_group.call_args.kwargs["message"]

    async def test_stop_requires_idle_probe_and_internal_probe_does_not_hide_result(
        self,
    ):
        running = self.submit()
        stop = self.submit("停止")
        self.store.report(self.key, self.device, stop, "SUCCESS", "")
        await self.tick()
        self.bot.send_to_group.assert_not_awaited()
        self.now += 6
        await self.tick()
        probe = self.connect()["tasks"][0]
        assert probe["type"] == "HeartBeat"
        assert self.store.view(self.owner)[1]["id"] == stop
        self.store.report(self.key, self.device, probe["id"], "SUCCESS", running)
        await self.tick()
        self.bot.send_to_group.assert_not_awaited()
        self.now += 11
        await self.tick()
        probe = self.connect()["tasks"][0]
        self.store.report(self.key, self.device, probe["id"], "SUCCESS", "")
        # MAA can report the original command before or after the stop probe.
        self.store.report(self.key, self.device, running, "SUCCESS", "")
        await self.tick()
        texts = [call.kwargs["message"] for call in self.bot.send_to_group.call_args_list]
        assert len(texts) == 2
        assert all("已停止" in text for text in texts)
        assert all("空闲" in text for text in texts)
        assert self.notices(stop)[0]["version"] == "stopped"

    async def test_stop_without_confirmation_and_disconnect_are_not_claimed_completed(
        self,
    ):
        running = self.submit()
        self.now += 61
        await self.tick()
        assert "连接中断" in self.bot.send_to_group.call_args.kwargs["message"]
        self.connect()
        stop = self.submit("停止")
        self.store.report(self.key, self.device, stop, "SUCCESS", "")
        self.now += 91
        await self.tick()
        assert self.notices(stop)[0]["version"] == "stop_unconfirmed"
        assert "停止尚未确认" in self.notices(stop)[0]["text"]
        assert self.notices(running)[0]["version"] == "offline"

    async def test_cancel_expiry_and_timeout_are_delivered_and_late_report_updates(
        self,
    ):
        cancelled = self.store.enqueue(self.owner, "基建", self.origin)
        self.store.enqueue(self.owner, "停止", self.origin)
        await self.tick()
        assert self.notices(cancelled)[0]["version"] == "cancelled"
        self.now += 121
        await self.tick()
        assert "过期" in self.bot.send_to_group.call_args.kwargs["message"]
        self.connect()
        task = self.submit()
        self.now += 3601
        await self.tick()
        assert self.notices(task)[0]["version"] == "unknown"
        assert "已终止" not in self.notices(task)[0]["text"]
        self.store.report(self.key, self.device, task, "SUCCESS", "")
        await self.tick()
        assert [n["version"] for n in self.notices(task)] == ["unknown", "ended"]

    async def test_private_image_retry_keeps_text_progress_and_failure_is_queryable(
        self,
    ):
        task = self.submit("截图", {"bot_id": "bot", "scene": "private", "target": "alice"})
        self.store.report(self.key, self.device, task, "SUCCESS", self.screenshot_payload())

        class Denied(Exception):
            code = 40034105

        async def sending(**kwargs):
            if not isinstance(kwargs["message"], str):
                raise Denied("do-not-log-this-secret")

        self.bot.send_to_c2c.side_effect = sending
        await self.tick()
        assert self.notices(task)[0]["text_sent"] == 1
        self.pump = Notifications(Store(self.temp.name, lambda: self.now), self.log)
        self.now += 31
        await self.tick()
        self.now += 121
        await self.tick()
        notice = self.notices(task)[0]
        assert (notice["status"], notice["attempts"]) == ("failed", 3)
        assert sum(isinstance(c.kwargs["message"], str) for c in self.bot.send_to_c2c.call_args_list) == 1
        text, image = self.commands.handle("结果", True, self.owner)
        assert "主动通知发送失败" in text
        assert "40034105" in text
        assert image.is_file()
        assert "do-not-log-this-secret" not in repr(self.log.mock_calls)
        self.bot.send_to_group.assert_not_awaited()

    async def test_disconnected_bot_waits_and_unbind_cascades_pending_notifications(
        self,
    ):
        task = self.submit()
        self.store.report(self.key, self.device, task, "FAILED", "")
        await self.pump.tick({})
        assert self.notices(task)[0]["attempts"] == 0
        self.store.revoke(self.owner)
        await self.tick()
        self.bot.send_to_group.assert_not_awaited()
        assert self.notices(task) == []

    async def test_late_final_report_supersedes_unsent_disconnect_notice(self):
        task = self.submit()
        self.now += 61
        await self.pump.tick({})
        assert self.notices(task)[0]["version"] == "offline"
        self.store.report(self.key, self.device, task, "SUCCESS", "")
        await self.tick()
        self.bot.send_to_group.assert_awaited_once()
        assert "执行已结束" in self.bot.send_to_group.call_args.kwargs["message"]
        assert [n["status"] for n in self.notices(task)] == ["superseded", "sent"]

    async def test_three_day_retention_cascades_origin_outbox_images_and_tmp(self):
        task = self.submit("截图")
        self.store.report(self.key, self.device, task, "SUCCESS", self.screenshot_payload())
        await self.pump.tick({})
        image = self.store.images / (task + ".jpg")
        temporary = self.store.images / "interrupted.tmp"
        temporary.write_text("incomplete", encoding="utf-8")
        for path in [image, temporary]:
            os.utime(path, (self.now, self.now))
        self.now += RETENTION + 1
        self.store.cleanup()
        with self.store.db() as db:
            for table in ["task", "task_origin", "task_notice", "audit"]:
                assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        assert not image.exists()
        assert not temporary.exists()
        assert self.store.view(self.owner)[0] is not None


if __name__ == "__main__":
    unittest.main(verbosity=2)
