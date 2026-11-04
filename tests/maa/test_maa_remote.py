import io
import os
import stat
import base64
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from PIL import Image
from fastapi import FastAPI
import bootstrap  # noqa: F401
from protocol import install_routes
from maa.commands import Commands, validate_base_url
from maa.core import RETENTION, Store, RemoteError, digest


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.now = 2_000_000_000
        self.store = Store(self.temp.name, lambda: self.now)
        self.commands = Commands(self.store, "https://bot.example.test")
        self.owner = digest("bot:c2c:alice")
        self.key = self.store.issue(self.owner)
        self.device = "maa-device-alice"

    def tearDown(self):
        self.temp.cleanup()

    def connect(self):
        return self.store.poll(self.key, self.device)

    def screenshot_payload(self):
        data = io.BytesIO()
        Image.new("RGB", (128, 72), (20, 40, 60)).save(data, "PNG")
        return base64.b64encode(data.getvalue()).decode()


class StateTests(Fixture):
    def test_reopen_group_owned_database_does_not_require_chmod(self):
        original_stat = Path.stat

        def shared_permissions(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            if path == self.store.path:
                fields = list(result)
                fields[0] = stat.S_IFREG | 0o660
                return os.stat_result(fields)
            return result

        with (
            patch.object(Path, "stat", shared_permissions),
            patch.object(Path, "chmod", side_effect=PermissionError("not the owner")) as chmod,
        ):
            reopened = Store(self.temp.name, lambda: self.now)
            assert reopened.view(self.owner)[0] is not None
            chmod.assert_not_called()

    def test_group_controls_own_device_but_never_issues_binding_key(self):
        self.connect()
        reply, _ = self.commands.handle("开始", False, self.owner, argument="基建")
        assert "已提交" in reply
        assert self.connect()["tasks"][0]["type"] == "LinkStart-Base"
        reply, _ = self.commands.handle("绑定", False, self.owner)
        assert "仅限私聊" in reply
        assert self.key not in reply
        reply, _ = self.commands.handle("状态", False, digest("bot:c2c:bob"))
        assert "尚未绑定" in reply

    def test_certificate_hidden_and_superuser_only(self):
        import json

        from maa.commands import HELP

        assert "/MAA证书" not in HELP
        reply, _ = self.commands.handle("证书", True, self.owner)
        assert "仅限超级用户" in reply
        (self.store.directory / "tls_status.json").write_text(
            json.dumps(
                {
                    "expires_at": self.now + 100 * 3600,
                    "checked_at": self.now,
                    "warning": False,
                }
            ),
            encoding="utf-8",
        )
        reply, _ = self.commands.handle("证书", True, self.owner, superuser=True)
        assert "100 小时" in reply

    def test_same_user_private_binding_works_in_group_without_link(self):
        self.connect()
        private, _ = self.commands.handle("状态", True, self.owner)
        group, _ = self.commands.handle("状态", False, self.owner)
        assert private == group
        assert "在线" in group

    def test_group_cannot_configure_binding_or_revoke(self):
        self.connect()
        before = self.store.path.read_bytes()
        for text in [
            "绑定",
            "解绑",
        ]:
            message, image = self.commands.handle(text, False, self.owner)
            assert "仅限私聊" in message
            assert image is None
        assert before == self.store.path.read_bytes()

    def test_owner_and_device_isolation(self):
        self.connect()
        bob = digest("bot:c2c:bob")
        other_key = self.store.issue(bob)
        self.store.poll(other_key, "bob-device")
        task = self.store.enqueue(self.owner, "截图")
        assert self.store.poll(other_key, "bob-device") == {"tasks": []}
        self.store.poll(self.key, self.device)
        with pytest.raises(RemoteError):
            self.store.report(other_key, "bob-device", task, "SUCCESS", self.screenshot_payload())
        with pytest.raises(RemoteError):
            self.store.poll(self.key, "another-device")
        assert self.store.view(bob)[1] is None

    def test_token_never_stored_plaintext_and_survives_restart(self):
        self.connect()
        assert self.key.encode() not in self.store.path.read_bytes()
        restarted = Store(self.temp.name, lambda: self.now)
        assert restarted.poll(self.key, self.device) == {"tasks": []}

    def test_pending_key_expiry_and_reissue_revokes_old(self):
        self.now += 901
        with pytest.raises(RemoteError):
            self.connect()
        new_key = self.store.issue(self.owner)
        with pytest.raises(RemoteError):
            self.connect()
        self.store.poll(new_key, self.device)
        with pytest.raises(RemoteError):
            self.store.issue(self.owner)

    def test_offline_does_not_enqueue(self):
        self.connect()
        self.now += 31
        with pytest.raises(RemoteError, match="离线"):
            self.store.enqueue(self.owner, "刷理智")
        assert self.store.view(self.owner)[1] is None

    def test_delivery_order_and_no_automatic_replay(self):
        self.connect()
        first = self.store.enqueue(self.owner, "基建")
        second = self.store.enqueue(self.owner, "截图")
        assert self.connect()["tasks"][0]["id"] == first
        assert self.connect()["tasks"][0]["id"] == second
        assert self.connect() == {"tasks": []}
        self.store.report(self.key, self.device, first, "SUCCESS", "")
        self.store.report(self.key, self.device, first, "SUCCESS", "")
        assert self.connect() == {"tasks": []}

    def test_unclaimed_tasks_expire(self):
        self.connect()
        self.store.enqueue(self.owner, "基建")
        self.now += 121
        assert self.connect() == {"tasks": []}
        assert self.store.view(self.owner)[1]["state"] == "expired"

    def test_lost_report_unknown_not_success_and_accept_late_report(self):
        self.connect()
        task = self.store.enqueue(self.owner, "基建")
        self.connect()
        self.now += 3601
        assert self.store.view(self.owner)[1]["state"] == "unknown"
        self.store.report(self.key, self.device, task, "SUCCESS", "")
        assert "不代表游戏任务实际成功" in self.store.view(self.owner)[1]["summary"]

    def test_stop_cancels_only_own_waiting_tasks(self):
        self.connect()
        old = self.store.enqueue(self.owner, "基建")
        stop = self.store.enqueue(self.owner, "停止")
        assert self.connect()["tasks"] == [{"id": stop, "type": "StopTask"}]
        with self.store.db() as db:
            assert db.execute("SELECT state FROM task WHERE id=?", (old,)).fetchone()[0] == "cancelled"

    def test_valid_image_and_unbind_revokes_key_and_removes_image(self):
        self.connect()
        task = self.store.enqueue(self.owner, "截图")
        self.connect()
        self.store.report(self.key, self.device, task, "SUCCESS", self.screenshot_payload())
        message, image = self.commands.handle("结果", True, self.owner)
        assert "已取得模拟器截图" in message
        assert image.is_file()
        self.store.revoke(self.owner)
        assert not image.exists()
        with pytest.raises(RemoteError):
            self.connect()

    def test_invalid_image_is_failure_and_payload_not_saved(self):
        self.connect()
        task = self.store.enqueue(self.owner, "截图")
        self.connect()
        payload = "not_an_image_and_secret"
        self.store.report(self.key, self.device, task, "SUCCESS", payload)
        assert self.store.view(self.owner)[1]["state"] == "failed"
        assert payload.encode() not in self.store.path.read_bytes()
        assert list(self.store.images.iterdir()) == []

    def test_retention_keeps_binding_but_deletes_old_history_and_images(self):
        self.connect()
        task = self.store.enqueue(self.owner, "截图")
        self.connect()
        self.store.report(self.key, self.device, task, "SUCCESS", self.screenshot_payload())
        path = self.store.images / (task + ".jpg")
        os.utime(path, (self.now, self.now))
        self.now += RETENTION + 1
        self.store.cleanup()
        assert not path.exists()
        assert self.store.view(self.owner)[1] is None
        assert self.store.view(self.owner)[0] is not None
        with self.store.db() as db:
            assert db.execute("SELECT COUNT(*) FROM audit").fetchone()[0] == 0

    def test_public_url_must_be_https_except_loopback(self):
        for url in [
            "http://example.com",
            "https://user:pass@example.com",
            "https://example.com/?key=a",
            "",
        ]:
            with pytest.raises(RemoteError):
                validate_base_url(url)
        assert validate_base_url("http://127.0.0.1:8765/") == "http://127.0.0.1:8765"

    def test_binding_output_only_private_and_no_secret_in_status(self):
        message, _ = self.commands.handle("绑定", True, self.owner)
        key = message.split("用户标识符：")[1].splitlines()[0]
        self.store.poll(key, self.device)
        status, _ = self.commands.handle("状态", True, self.owner)
        assert key not in status
        assert self.device not in status
        assert "在线" in status

    def test_duplicate_qq_event_does_not_enqueue_again(self):
        self.connect()
        self.commands.handle("开始", True, self.owner, "qq-message-1", argument="基建")
        reply, _ = self.commands.handle("开始", True, self.owner, "qq-message-1", argument="基建")
        assert "已经处理过" in reply
        assert len(self.connect()["tasks"]) == 1
        assert self.connect()["tasks"] == []

    def test_one_execution_at_a_time_but_screenshot_and_stop_allowed(self):
        self.connect()
        self.store.enqueue(self.owner, "基建")
        self.connect()
        with pytest.raises(RemoteError, match="已有执行任务"):
            self.store.enqueue(self.owner, "刷理智")
        self.store.enqueue(self.owner, "截图")
        self.store.enqueue(self.owner, "停止")

    def test_empty_heartbeat_clears_busy_without_claiming_original_success(self):
        self.connect()
        task = self.store.enqueue(self.owner, "基建")
        self.connect()
        heartbeat = self.store.enqueue(self.owner, "心跳")
        self.connect()
        self.store.report(self.key, self.device, heartbeat, "SUCCESS", "")
        with self.store.db() as db:
            row = db.execute("SELECT state,summary FROM task WHERE id=?", (task,)).fetchone()
            assert row["state"] == "unconfirmed"
            assert "未确认" in row["summary"]
        self.store.enqueue(self.owner, "刷理智")


class HttpTests(Fixture, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = FastAPI()
        install_routes(self.app, self.store)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="https://test")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_official_maa_wire_format_round_trip(self):
        auth = {"user": self.key, "device": self.device}
        response = await self.client.post("/maa/getTask", json=auth)
        assert response.status_code == 200
        assert response.json() == {"tasks": []}
        task = self.store.enqueue(self.owner, "截图")
        response = await self.client.post("/maa/getTask", json=auth)
        assert response.json()["tasks"] == [{"id": task, "type": "CaptureImageNow"}]
        response = await self.client.post(
            "/maa/reportStatus",
            json={
                **auth,
                "task": task,
                "status": "SUCCESS",
                "payload": self.screenshot_payload(),
            },
        )
        assert response.status_code == 200
        assert self.commands.handle("结果", True, self.owner)[1].is_file()

    async def test_bad_requests_and_unknown_credentials_do_not_create_bindings(self):
        for body, code in [
            ([], 400),
            ({}, 403),
            ({"user": "x" * 43, "device": "bad"}, 403),
            ({"user": self.key, "device": []}, 403),
            ({"user": self.key, "device": "中文"}, 403),
        ]:
            response = await self.client.post("/maa/getTask", json=body)
            assert response.status_code == code
        response = await self.client.post("/maa/getTask", content=b"broken json")
        assert response.status_code == 400
        response = await self.client.post("/maa/getTask", content=b"x" * 4097)
        assert response.status_code == 413
        assert self.store.view(self.owner)[0]["device"] is None

    async def test_forged_and_malformed_report_rejected(self):
        self.connect()
        task = self.store.enqueue(self.owner, "心跳")
        self.connect()
        auth = {"user": self.key, "device": self.device, "task": task, "payload": ""}
        for status in [[], {}, None, "INVALID"]:
            response = await self.client.post("/maa/reportStatus", json={**auth, "status": status})
            assert response.status_code == 403
        response = await self.client.post("/maa/reportStatus", json={**auth, "task": "f" * 32, "status": "SUCCESS"})
        assert response.status_code == 403
        assert self.store.view(self.owner)[1]["state"] == "dispatched"

    async def test_unauthorized_stream_stopped_before_image_body(self):
        consumed = []

        async def stream():
            consumed.append("header")
            yield (
                b'{"user":"invalid-key","device":"bad","status":"SUCCESS",'
                b'"task":"00000000000000000000000000000000","payload":"'
            )
            consumed.append("body")
            yield b"x" * 1000000

        response = await self.client.post("/maa/reportStatus", content=stream())
        assert response.status_code == 403
        assert consumed == ["header"]

    async def test_split_header_and_real_maa_field_order(self):
        import json

        self.connect()
        task = self.store.enqueue(self.owner, "截图")
        self.connect()
        raw = json.dumps(
            {
                "user": self.key,
                "device": self.device,
                "status": "SUCCESS",
                "task": task,
                "payload": self.screenshot_payload(),
            }
        ).encode()

        async def stream():
            for i in range(0, len(raw), 13):
                yield raw[i : i + 13]

        response = await self.client.post("/maa/reportStatus", content=stream())
        assert response.status_code == 200
        assert self.commands.handle("结果", True, self.owner)[1].exists()

    async def test_upload_slots_reject_third_request(self):
        import json

        self.connect()
        task = self.store.enqueue(self.owner, "截图")
        self.connect()
        header = (
            json.dumps(
                {
                    "user": self.key,
                    "device": self.device,
                    "status": "SUCCESS",
                    "task": task,
                }
            )[:-1].encode()
            + b',"payload":"'
        )
        release = asyncio.Event()
        ready = [asyncio.Event(), asyncio.Event()]

        async def stream(n):
            yield header
            ready[n].set()
            await release.wait()
            yield self.screenshot_payload().encode() + b'"}'

        jobs = [asyncio.create_task(self.client.post("/maa/reportStatus", content=stream(n))) for n in range(2)]
        try:
            await asyncio.wait_for(asyncio.gather(*(x.wait() for x in ready)), 3)
            response = await self.client.post("/maa/reportStatus", content=header)
            assert response.status_code == 429
        finally:
            release.set()
            await asyncio.gather(*jobs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
