"""Offline checks for the root-only renewal template; never run Certbot."""

import os
import ssl
import json
import stat
import tempfile
import unittest
import subprocess
import importlib.util
from pathlib import Path
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "examples/maa/renew_certificate.py"
spec = importlib.util.spec_from_file_location("maa_renew_certificate_example", SCRIPT)
renewal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renewal)


class RenewalTests(unittest.TestCase):
    def setUp(self):
        self.environment = {
            "MAA_CERTBOT_BIN": "/usr/bin/certbot",
            "MAA_CERT_NAME": "maa.example.com-0001",
            "MAA_CERTBOT_LOG_DIR": "/var/log/maa certbot",
            "MAA_NGINX_RELOAD": "/usr/bin/systemctl reload nginx",
        }

    def test_command_keeps_option_values_separate_from_flags(self):
        command = renewal.renewal_command(self.environment)
        assert command[0] == "/usr/bin/certbot"
        assert "--cert-name=maa.example.com-0001" in command
        assert "--logs-dir=/var/log/maa certbot" in command
        assert command[-2:] == ["--deploy-hook", "/usr/bin/systemctl reload nginx"]

    def test_hook_quotes_metacharacters_as_one_literal_argument(self):
        command = renewal.renewal_command(
            {**self.environment, "MAA_NGINX_RELOAD": '/usr/bin/systemctl reload "nginx;$(touch /tmp/maa-test)"'}
        )
        assert command[-1] == "/usr/bin/systemctl reload 'nginx;$(touch /tmp/maa-test)'"
        command = renewal.renewal_command(
            {**self.environment, "MAA_NGINX_RELOAD": '"/opt/maa tools/reload" "nginx service"'}
        )
        assert command[-1] == "'/opt/maa tools/reload' 'nginx service'"

    def test_rejects_relative_executables_and_invalid_configuration(self):
        for key, value in (
            ("MAA_CERTBOT_BIN", "certbot"),
            ("MAA_CERTBOT_LOG_DIR", "logs"),
            ("MAA_NGINX_RELOAD", "systemctl reload nginx"),
            ("MAA_NGINX_RELOAD", ""),
            ("MAA_NGINX_RELOAD", '"unterminated'),
            ("MAA_CERT_NAME", "--deploy-hook=malicious"),
            ("MAA_CERT_NAME", "maa; command"),
        ):
            with (
                self.subTest(key=key, value=value),
                pytest.raises(
                    ValueError, match="absolute POSIX paths|invalid MAA certificate name|No closing quotation"
                ),
            ):
                renewal.renewal_command({**self.environment, key: value})

    def test_main_publishes_only_status_on_success_failure_and_timeout(self):
        now = 2_000_000_000
        cases = (
            (SimpleNamespace(returncode=0, stdout=b"private output", stderr=b"private error"), None, None, 0),
            (SimpleNamespace(returncode=1), None, None, 1),
            (None, subprocess.TimeoutExpired("certbot", 180), None, 1),
            (SimpleNamespace(returncode=0), None, ssl.SSLError("private certificate error"), 1),
        )
        environment = {
            **self.environment,
            "MAA_CERT_CHAIN": "/etc/letsencrypt/live/maa.example.com/fullchain.pem",
            "MAA_REMOTE_DATA_DIR": "/var/lib/skland-maa",
            "MAA_RENEW_STAGING_DIR": "/var/lib/maa-renew-private",
        }
        for result, error, cert_error, expected in cases:
            with (
                self.subTest(expected=expected, error=type(error).__name__),
                patch.dict(os.environ, environment, clear=True),
                patch.object(renewal.subprocess, "run", return_value=result, side_effect=error) as run,
                patch.object(
                    renewal.ssl._ssl,
                    "_test_decode_cert",
                    return_value={"notAfter": "unused"},
                    side_effect=cert_error,
                ),
                patch.object(renewal.ssl, "cert_time_to_seconds", return_value=now + 72 * 3600),
                patch.object(renewal.time, "time", return_value=now),
                patch.object(renewal.Path, "glob", return_value=[]),
                patch.object(renewal, "publish_status") as publish,
                patch.object(renewal.logging, "basicConfig"),
                patch.object(renewal.logging, "info") as log,
            ):
                assert renewal.main() == expected
                run.assert_called_once_with(
                    renewal.renewal_command(environment), shell=False, capture_output=True, timeout=180, check=False
                )
                publish.assert_called_once()
                assert publish.call_args.args[0] == Path(environment["MAA_REMOTE_DATA_DIR"]) / "tls_status.json"
                assert publish.call_args.args[2] == Path(environment["MAA_RENEW_STAGING_DIR"])
                state = publish.call_args.args[1]
                assert set(state) == {"checked_at", "expires_at", "renew_ok", "warning"}
                assert state["warning"] is bool(expected)
                assert state["renew_ok"] is (error is None and result.returncode == 0)
                assert "private" not in repr(log.mock_calls)


class PublishStatusTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        for name, value in (("O_DIRECTORY", 0x10000), ("O_NOFOLLOW", 0x20000)):
            stack.enter_context(patch.object(renewal.os, name, value, create=True))
        self.calls = {
            name: stack.enter_context(patch.object(renewal.os, name, create=True))
            for name in ("open", "fstat", "fdopen", "fchown", "fchmod", "replace", "close")
        }
        self.calls["open"].return_value = 100
        self.open_directory = stack.enter_context(patch.object(renewal, "open_directory", return_value=100))
        self.calls["fstat"].return_value = SimpleNamespace(st_dev=1, st_gid=42)
        self.output = self.calls["fdopen"].return_value.__enter__.return_value
        self.output.fileno.return_value = 101
        self.mkstemp = stack.enter_context(patch.object(renewal.tempfile, "mkstemp"))
        self.mkstemp.return_value = (101, "/private/tls-status-random.tmp")
        self.unlink = stack.enter_context(patch.object(renewal.Path, "unlink"))
        self.staging = Mock()
        self.staging.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=0, st_dev=1)
        self.status = Path("/shared/tls_status.json")

    def test_publication_uses_private_temp_and_pinned_destination(self):
        state = {"renew_ok": True}
        renewal.publish_status(self.status, state, self.staging)
        self.open_directory.assert_called_once_with(self.status.parent)
        self.calls["open"].assert_not_called()
        self.mkstemp.assert_called_once_with(prefix="tls-status-", suffix=".tmp", dir=self.staging)
        assert json.loads(self.output.write.call_args.args[0]) == state
        self.calls["fchown"].assert_called_once_with(101, -1, 42)
        self.calls["fchmod"].assert_called_once_with(101, 0o640)
        self.calls["replace"].assert_called_once_with(
            "/private/tls-status-random.tmp", "tls_status.json", dst_dir_fd=100
        )
        self.unlink.assert_called_once_with(missing_ok=True)
        self.calls["close"].assert_called_once_with(100)

    def test_rejects_non_private_or_symlink_staging_before_opening_files(self):
        for mode, uid in ((stat.S_IFDIR | 0o777, 0), (stat.S_IFDIR | 0o700, 1000), (stat.S_IFLNK | 0o700, 0)):
            self.staging.lstat.return_value = SimpleNamespace(st_mode=mode, st_uid=uid, st_dev=1)
            with pytest.raises(ValueError, match="root-owned"):
                renewal.publish_status(self.status, {}, self.staging)
        self.calls["open"].assert_not_called()
        self.open_directory.assert_not_called()
        self.mkstemp.assert_not_called()

    def test_cross_filesystem_configuration_is_rejected_without_temp_file(self):
        self.calls["fstat"].return_value.st_dev = 2
        with pytest.raises(ValueError, match="same filesystem"):
            renewal.publish_status(self.status, {}, self.staging)
        self.mkstemp.assert_not_called()
        self.calls["close"].assert_called_once_with(100)

    def test_failed_publication_cleans_up_private_file_and_descriptor(self):
        self.calls["replace"].side_effect = OSError("replace failed")
        with pytest.raises(OSError, match="replace failed"):
            renewal.publish_status(self.status, {}, self.staging)
        self.unlink.assert_called_once_with(missing_ok=True)
        self.calls["close"].assert_called_once_with(100)


class DirectoryOpenTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        for name, value in (("O_DIRECTORY", 0x10000), ("O_NOFOLLOW", 0x20000)):
            stack.enter_context(patch.object(renewal.os, name, value, create=True))
        self.open = stack.enter_context(patch.object(renewal.os, "open"))
        self.close = stack.enter_context(patch.object(renewal.os, "close"))

    def test_each_directory_component_is_opened_without_following_links(self):
        self.open.side_effect = [10, 11, 12]
        assert renewal.open_directory(Path("/shared/nested")) == 12
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        assert self.open.call_args_list == [
            call("/", flags),
            call("shared", flags, dir_fd=10),
            call("nested", flags, dir_fd=11),
        ]
        assert self.close.call_args_list == [call(10), call(11)]

    def test_failed_component_closes_descriptor(self):
        self.open.side_effect = [10, OSError("symlink refused")]
        with pytest.raises(OSError, match="symlink refused"):
            renewal.open_directory(Path("/shared/nested"))
        self.close.assert_called_once_with(10)

    def test_relative_and_parent_traversal_paths_are_rejected(self):
        for path in (Path("relative"), Path("/shared/../other")):
            with pytest.raises(ValueError, match="absolute path"):
                renewal.open_directory(path)
        self.open.assert_not_called()


@unittest.skipUnless(os.name == "posix", "requires POSIX directory descriptors and symlinks")
class PublicationFilesystemTests(unittest.TestCase):
    def test_planted_shared_symlinks_do_not_modify_their_target(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            staging, shared = base / "private", base / "shared"
            staging.mkdir(mode=0o700)
            shared.mkdir()
            victim = base / "victim"
            victim.write_text("unchanged", encoding="utf-8")
            (shared / "tls_status.tmp").symlink_to(victim)
            status = shared / "tls_status.json"
            status.symlink_to(victim)
            original_lstat = Path.lstat

            def service_stat(path, *args, **kwargs):
                info = original_lstat(path, *args, **kwargs)
                if path == staging:
                    return SimpleNamespace(st_mode=info.st_mode, st_uid=0, st_dev=info.st_dev)
                return info

            with patch.object(Path, "lstat", service_stat):
                renewal.publish_status(status, {"renew_ok": True}, staging)
            assert victim.read_text(encoding="utf-8") == "unchanged"
            assert not status.is_symlink()
            assert json.loads(status.read_text(encoding="utf-8")) == {"renew_ok": True}
            assert (shared / "tls_status.tmp").is_symlink()
            assert list(staging.iterdir()) == []


if __name__ == "__main__":
    unittest.main()
