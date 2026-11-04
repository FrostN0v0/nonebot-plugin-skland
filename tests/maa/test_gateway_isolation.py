import os
import sys
import tempfile
import unittest
import subprocess
from pathlib import Path

import bootstrap


class GatewayIsolationTests(unittest.TestCase):
    def test_gateway_import_does_not_load_nonebot_or_skland(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = {**os.environ, "MAA_REMOTE_DATA_DIR": directory, "PYTHONPATH": str(bootstrap.DIRECTORY)}
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import gateway, sys; "
                    "assert 'nonebot' not in sys.modules; "
                    "assert 'nonebot_plugin_skland' not in sys.modules; "
                    "assert {r.path for r in gateway.app.routes} == {'/maa/getTask', '/maa/reportStatus'}",
                ],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, result.stderr
            assert (Path(directory) / "maa.sqlite3").is_file()
