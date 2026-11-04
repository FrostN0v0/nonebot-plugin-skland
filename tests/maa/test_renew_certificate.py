"""Offline checks for the root-only renewal template; never run Certbot."""

import os
import ssl
import json
import unittest
import subprocess
import importlib.util
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

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
                patch.object(renewal.Path, "write_text") as write,
                patch.object(renewal.Path, "replace"),
                patch.object(renewal.os, "chmod"),
                patch.object(renewal.logging, "basicConfig"),
                patch.object(renewal.logging, "info") as log,
            ):
                assert renewal.main() == expected
                run.assert_called_once_with(
                    renewal.renewal_command(environment), shell=False, capture_output=True, timeout=180, check=False
                )
                write.assert_called_once()
                state = json.loads(write.call_args.args[0])
                assert set(state) == {"checked_at", "expires_at", "renew_ok", "warning"}
                assert state["warning"] is bool(expected)
                assert state["renew_ok"] is (error is None and result.returncode == 0)
                assert "private" not in repr(log.mock_calls)


if __name__ == "__main__":
    unittest.main()
