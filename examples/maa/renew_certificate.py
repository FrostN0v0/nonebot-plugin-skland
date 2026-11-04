"""Root-only renewal; publish expiry status without certificate or account data."""

import os
import re
import ssl
import json
import time
import shlex
import logging
import subprocess
from pathlib import Path, PurePosixPath


def renewal_command(environment):
    certbot = environment["MAA_CERTBOT_BIN"]
    cert_name = environment["MAA_CERT_NAME"]
    log_dir = environment["MAA_CERTBOT_LOG_DIR"]
    reload_args = shlex.split(environment["MAA_NGINX_RELOAD"])
    if not reload_args or not all(PurePosixPath(path).is_absolute() for path in (certbot, reload_args[0], log_dir)):
        raise ValueError("MAA renewal executables and log directory must use absolute POSIX paths")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", cert_name):
        raise ValueError("invalid MAA certificate name")
    # Only root-managed configuration is trusted. Certbot executes this hook in a
    # POSIX shell, so encode one argv command instead of forwarding shell syntax.
    return [
        certbot,
        "renew",
        "--quiet",
        f"--cert-name={cert_name}",
        "--max-log-backups",
        "3",
        f"--logs-dir={log_dir}",
        "--deploy-hook",
        shlex.join(reload_args),
    ]


def main():
    cert = Path(os.environ["MAA_CERT_CHAIN"])
    status = Path(os.environ["MAA_REMOTE_DATA_DIR"]) / "tls_status.json"
    command = renewal_command(os.environ)
    try:
        result = subprocess.run(command, shell=False, capture_output=True, timeout=180, check=False)
        code = result.returncode
    except subprocess.TimeoutExpired:
        code = 124
    try:
        decoded = ssl._ssl._test_decode_cert(str(cert))
        expires = ssl.cert_time_to_seconds(decoded["notAfter"])
    except (OSError, ssl.SSLError, ValueError):
        expires = 0
    state = {
        "checked_at": time.time(),
        "expires_at": expires,
        "renew_ok": code == 0,
        "warning": code != 0 or expires - time.time() < 36 * 3600,
    }
    temporary = status.with_suffix(".tmp")
    temporary.write_text(json.dumps(state) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o640)
    temporary.replace(status)
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
    return 1 if state["warning"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
