import unittest

import pytest
import bootstrap  # noqa: F401
from maa.core import RemoteError
from maa.commands import validate_base_url


class UrlPolicyTests(unittest.TestCase):
    def test_malformed_urls_and_path_prefixes_report_configuration_errors(self):
        for value in (
            "https://[::1",
            "https://[not-ip]/",
            "https://maa.example.com:invalid",
            "https://maa.example.com:99999",
            "https://maa.example.com/prefix",
            "https://maa.example.com/maa/getTask",
            "https://maa.example.com/?",
            "https://maa.example.com/#",
            "https://:443",
        ):
            with self.subTest(value=value), pytest.raises(RemoteError, match="public_url"):
                validate_base_url(value)

    def test_root_endpoints_keep_explicit_ports_and_allow_loopback_tests(self):
        assert validate_base_url("https://maa.example.com:443/") == "https://maa.example.com:443"
        assert validate_base_url("http://[::1]:8765/") == "http://[::1]:8765"
