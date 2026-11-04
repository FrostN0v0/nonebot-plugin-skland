"""Root-only renewal; publish expiry status without certificate or account data."""

import os
import ssl
import json
import time
import logging
import subprocess
from pathlib import Path

CERT = Path(os.environ["MAA_CERT_CHAIN"])
STATUS = Path(os.environ["MAA_REMOTE_DATA_DIR"]) / "tls_status.json"
command = [
    os.environ["MAA_CERTBOT_BIN"],
    "renew",
    "--quiet",
    "--cert-name",
    os.environ["MAA_CERT_NAME"],
    "--max-log-backups",
    "3",
    "--logs-dir",
    os.environ["MAA_CERTBOT_LOG_DIR"],
    "--deploy-hook",
    os.environ["MAA_NGINX_RELOAD"],
]
try:
    result = subprocess.run(command, capture_output=True, timeout=180, check=False)
    code = result.returncode
except subprocess.TimeoutExpired:
    code = 124
try:
    decoded = ssl._ssl._test_decode_cert(str(CERT))
    expires = ssl.cert_time_to_seconds(decoded["notAfter"])
except (OSError, ssl.SSLError, ValueError):
    expires = 0
state = {
    "checked_at": time.time(),
    "expires_at": expires,
    "renew_ok": code == 0,
    "warning": code != 0 or expires - time.time() < 36 * 3600,
}
temporary = STATUS.with_suffix(".tmp")
temporary.write_text(json.dumps(state) + "\n", encoding="utf-8")
os.chmod(temporary, 0o640)
temporary.replace(STATUS)
for path in Path(os.environ["MAA_CERTBOT_LOG_DIR"]).glob("letsencrypt.log*"):
    if path.stat().st_mtime < time.time() - 3 * 86400:
        path.unlink()
logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.info(
    "MAA certificate renewal exit=%s, remaining_hours=%s, warning=%s",
    code,
    max(0, int((expires - time.time()) / 3600)),
    state["warning"],
)
raise SystemExit(1 if state["warning"] else 0)
