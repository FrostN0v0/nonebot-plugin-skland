"""Root-only status publisher, invoked by the renewal unit's ExecStopPost."""

import os
import ssl
import json
import stat
import time
import logging
import tempfile
from pathlib import Path, PurePosixPath


def renewal_succeeded(environment):
    return (
        environment.get("SERVICE_RESULT") == "success"
        and environment.get("EXIT_CODE") == "exited"
        and environment.get("EXIT_STATUS") == "0"
    )


def open_directory(path):
    path = PurePosixPath(path.as_posix())
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("MAA status directory must use an absolute path without parent traversal")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", flags)
    try:
        for part in path.parts[1:]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def publish_status(status, state, staging):
    staging_info = staging.lstat()
    if (
        not stat.S_ISDIR(staging_info.st_mode)
        or staging_info.st_uid != 0
        or stat.S_IMODE(staging_info.st_mode) != 0o700
    ):
        raise ValueError("MAA renewal staging directory must be root-owned with mode 0700")
    # Pin the destination directory; replacing the final entry never follows a
    # planted tls_status.json symlink. Temporary files stay outside the shared tree.
    directory_fd = open_directory(status.parent)
    try:
        destination = os.fstat(directory_fd)
        if staging_info.st_dev != destination.st_dev:
            raise ValueError("MAA renewal staging and data directories must be on the same filesystem")
        fd, temporary = tempfile.mkstemp(prefix="tls-status-", suffix=".tmp", dir=staging)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                output.write(json.dumps(state) + "\n")
                os.fchown(output.fileno(), -1, destination.st_gid)
                os.fchmod(output.fileno(), 0o640)
            os.replace(temporary, status.name, dst_dir_fd=directory_fd)
        finally:
            Path(temporary).unlink(missing_ok=True)
    finally:
        os.close(directory_fd)


def main():
    cert = Path(os.environ["MAA_CERT_CHAIN"])
    status = Path(os.environ["MAA_REMOTE_DATA_DIR"]) / "tls_status.json"
    renewed = renewal_succeeded(os.environ)
    try:
        decoded = ssl._ssl._test_decode_cert(str(cert))
        expires = ssl.cert_time_to_seconds(decoded["notAfter"])
    except (OSError, ssl.SSLError, ValueError):
        expires = 0
    state = {
        "checked_at": time.time(),
        "expires_at": expires,
        "renew_ok": renewed,
        "warning": not renewed or expires - time.time() < 36 * 3600,
    }
    publish_status(status, state, Path(os.environ["MAA_RENEW_STAGING_DIR"]))
    for path in Path(os.environ["MAA_CERTBOT_LOG_DIR"]).glob("letsencrypt.log*"):
        if path.stat().st_mtime < time.time() - 3 * 86400:
            path.unlink()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.info(
        "MAA certificate renewal ok=%s, remaining_hours=%s, warning=%s",
        renewed,
        max(0, int((expires - time.time()) / 3600)),
        state["warning"],
    )
    return 1 if state["warning"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
