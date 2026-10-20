"""Atomic publication of individual binary files."""

import os
from pathlib import Path
from typing import BinaryIO
from collections.abc import Iterator
from tempfile import NamedTemporaryFile
from contextlib import suppress, contextmanager


@contextmanager
def atomic_write(path: Path) -> Iterator[BinaryIO]:
    """Publish a same-directory temporary file only after a successful write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    )
    temporary_path = Path(temporary_file.name)
    try:
        with temporary_file as file:
            yield file
        os.replace(temporary_path, path)
    except BaseException:
        with suppress(OSError):
            temporary_path.unlink(missing_ok=True)
        raise
