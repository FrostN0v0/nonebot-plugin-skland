"""Browser isolation, original QQ owner, one-time keys and first-device enforcement."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import bootstrap  # noqa: F401
from binding_web import create_app
from maa.core import Store, RemoteError
from binding_state import BindingError, BindingStore

DEVICE = "f7cd8461-7781-49b5-a219-e4fdc181e9ec"


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.now = 2_000_000_000
        self.remote = Store(Path(self.temp.name) / "remote", clock=lambda: self.now)
        self.pair = BindingStore(":memory:", self.remote.issue, "https://maa.example.com", clock=lambda: self.now)
        self.entry = self.pair.create("bot", "alice", "group:one", "alice-owner")

    def tearDown(self):
        self.pair.connection.close()
        self.temp.cleanup()

    def test_only_initiator_in_original_scene_can_confirm_only_selected_browser_gets_key(self):
        first = self.pair.submit(self.entry, "browser-one", DEVICE)
        second = self.pair.submit(self.entry, "browser-two", DEVICE)
        for bot, user, target in (
            ("other", "alice", "group:one"),
            ("bot", "bob", "group:one"),
            ("bot", "alice", "private:alice"),
            ("bot", "alice", "group:two"),
        ):
            assert not self.pair.decide(first["id"], True, bot, user, target)
        with pytest.raises(BindingError):
            self.pair.redeem(self.entry, "browser-one")
        assert self.pair.decide(first["id"], True, "bot", "alice", "group:one")
        assert not self.pair.decide(first["id"], True, "bot", "alice", "group:one")
        assert self.pair.status(self.entry, "browser-two")["state"] == "superseded"
        with pytest.raises(BindingError):
            self.pair.redeem(self.entry, "browser-two")
        settings = self.pair.redeem(self.entry, "browser-one")
        assert settings["key"].startswith("maa_")
        assert "key" not in self.pair.status(self.entry, "browser-one")
        with pytest.raises(BindingError):
            self.pair.redeem(self.entry, "browser-one")
        with pytest.raises(RemoteError):
            self.remote.poll(settings["key"], "wrong-device")
        assert self.remote.view("alice-owner")[0]["device"] is None
        assert self.remote.poll(settings["key"], DEVICE) == {"tasks": []}
        assert self.remote.view("alice-owner")[0]["device"] == DEVICE
        assert self.pair.status(self.entry, "browser-one")["state"] == "delivered"
        assert second["code"] != first["code"] or second["id"] != first["id"]

    def test_pending_expiry_legacy_compatibility_and_unbind_invalidates_approval(self):
        row = self.pair.submit(self.entry, "browser", DEVICE)
        assert self.pair.decide(row["id"], True, "bot", "alice", "group:one")
        settings = self.pair.redeem(self.entry, "browser")
        self.now += 901
        with pytest.raises(RemoteError):
            self.remote.poll(settings["key"], DEVICE)
        key = self.remote.issue("legacy-owner")
        assert self.remote.poll(key, "legacy-device") == {"tasks": []}
        self.pair.cleanup()
        assert self.pair.connection.execute("SELECT COUNT(*) FROM entry").fetchone()[0] == 0
        entry = self.pair.create("bot", "alice", "private:alice", "alice-owner")
        row = self.pair.submit(entry, "browser", DEVICE)
        assert self.pair.decide(row["id"], True, "bot", "alice", "private:alice")
        self.pair.invalidate("alice-owner")
        with pytest.raises(BindingError):
            self.pair.redeem(entry, "browser")

    def test_cancel_new_request_and_capacity(self):
        row = self.pair.submit(self.entry, "browser", DEVICE)
        assert self.pair.decide(row["id"], False, "bot", "alice", "group:one")
        with pytest.raises(BindingError):
            self.pair.redeem(self.entry, "browser")
        self.now += 11
        entry = self.pair.create("bot", "alice", "private:alice", "alice-owner")
        for number in range(3):
            self.pair.submit(entry, str(number), DEVICE)
        with pytest.raises(BindingError):
            self.pair.submit(entry, "fourth-browser", DEVICE)

    def test_new_link_revokes_previous_unclaimed_approval(self):
        row = self.pair.submit(self.entry, "old-browser", DEVICE)
        assert self.pair.decide(row["id"], True, "bot", "alice", "group:one")
        self.now += 11
        self.pair.create("bot", "alice", "private:alice", "alice-owner")
        with pytest.raises(BindingError):
            self.pair.redeem(self.entry, "old-browser")

    def test_web_cookies_origin_payload_and_no_key_in_status(self):
        async def scenario():
            async def broker(op, **kwargs):
                return getattr(self.pair, op)(*kwargs.values())

            app = create_app(broker, "https://maa.example.com")
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://maa.example.com"
            ) as web:
                response = await web.get("/maa/bind")
                assert "MAA设置-远程控制-设备标识符" in response.text
                assert response.headers["cache-control"] == "no-store"
                response = await web.post("/maa/bind/api/submit", json={"request": self.entry, "device": DEVICE})
                assert response.status_code == 403
                headers = {"origin": "https://maa.example.com"}
                response = await web.post(
                    "/maa/bind/api/submit", headers=headers, json={"request": self.entry, "device": DEVICE}
                )
                assert response.status_code == 200
                cookie = response.headers["set-cookie"]
                assert all(part in cookie for part in ("HttpOnly", "Secure", "SameSite=strict", "Path=/"))
                row = self.pair.latest("bot", "alice", "group:one")
                assert self.pair.decide(row["id"], True, "bot", "alice", "group:one")
                response = await web.get("/maa/bind/api/status", params={"entry": self.entry})
                assert response.json()["state"] == "approved"
                assert "key" not in response.json()
                response = await web.post("/maa/bind/api/redeem", params={"entry": self.entry}, headers=headers)
                assert response.status_code == 200
                assert response.json()["key"].startswith("maa_")
                assert (
                    await web.post("/maa/bind/api/redeem", params={"entry": self.entry}, headers=headers)
                ).status_code == 400
                assert (await web.post("/maa/bind/api/submit", headers=headers, content="x" * 2049)).status_code == 413

        asyncio.run(scenario())

    def test_broker_failure_is_sanitized(self):
        from binding_rpc import client

        async def scenario():
            with patch("asyncio.open_unix_connection", create=True, new=AsyncMock(side_effect=OSError)):
                with pytest.raises(BindingError, match="服务暂不可用"):
                    await client("missing-socket")("status", entry="entry", session="session")

        asyncio.run(scenario())
