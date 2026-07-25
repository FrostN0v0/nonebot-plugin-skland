"""Assemble still frames into a slideshow video via ffmpeg."""

from __future__ import annotations

import shutil
import asyncio
from pathlib import Path

COVER_DURATION = 5.0
OPERATOR_FRAME_DURATION = 2.0


class FFmpegNotFoundError(RuntimeError):
    """Raised when the ffmpeg executable is not available."""


def require_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise FFmpegNotFoundError("未找到 ffmpeg，请先安装并确保可在 PATH 中调用")
    return path


def write_concat_list(frames: list[tuple[Path, float]], list_path: Path) -> None:
    """Write an ffmpeg concat demuxer list with per-frame durations."""
    if not frames:
        raise ValueError("至少需要一帧才能生成视频")

    lines: list[str] = []
    for path, duration in frames:
        lines.append(f"file '{path.resolve().as_posix()}'")
        lines.append(f"duration {duration:g}")
    # ffmpeg image concat quirk: repeat the last file without duration
    lines.append(f"file '{frames[-1][0].resolve().as_posix()}'")
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def encode_slideshow(frames: list[tuple[Path, float]], output: Path) -> Path:
    """Encode PNG frames into a compact H.264 mp4 slideshow for chat clients."""
    ffmpeg = require_ffmpeg()
    list_path = output.with_suffix(".concat.txt")
    write_concat_list(frames, list_path)

    # Prefer smaller files for QQ / OneBot upload limits: 720p + capped bitrate.
    command = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-vf",
        "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
        "-vsync",
        "vfr",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "28",
        "-maxrate",
        "1500k",
        "-bufsize",
        "3000k",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        detail = stderr.decode(errors="ignore").strip() or f"exit code {process.returncode}"
        raise RuntimeError(f"ffmpeg 合成失败：{detail}")
    return output
