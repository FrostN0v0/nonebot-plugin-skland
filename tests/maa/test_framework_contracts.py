"""Verify disputed upstream behavior without writing files or starting a bot."""

import os
import json
import unittest
from pathlib import Path
from unittest.mock import patch, mock_open

from loguru._file_sink import FileSink
from nonebot.config import Config, DotEnvSettingsSource


class FrameworkContractTests(unittest.TestCase):
    def test_loguru_creates_parent_directories_for_a_file_sink(self):
        path = Path("maa-contract-test") / "logs/maa.log"
        with patch("loguru._file_sink.os.makedirs") as mkdir, patch("loguru._file_sink.open", mock_open(), create=True):
            sink = FileSink(path)
            mkdir.assert_called_once_with(str(path.absolute().parent), exist_ok=True)
            sink.stop()

    def test_nonebot_decodes_json_dotenv_custom_configuration(self):
        settings = {
            "maa": {"enabled": True, "public_url": "https://maa.example.com", "data_dir": "/var/lib/skland-maa"}
        }
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(DotEnvSettingsSource, "_read_env_files", return_value={"skland": json.dumps(settings)}),
        ):
            parsed = Config(_env_file=None)
        assert parsed.skland == settings
