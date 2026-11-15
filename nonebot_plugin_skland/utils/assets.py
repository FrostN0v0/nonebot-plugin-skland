"""定位本次新增卫戍素材，保留上游路径，不改变旧素材的读取方式。"""

import json
from typing import TypedDict
from urllib.parse import quote, urlsplit

from ..config import RES_DIR, IMAGE_DIR, config


class ImageSource(TypedDict):
    base_url: str
    files: dict[str, str]


IMAGE_SOURCES: dict[str, ImageSource] = json.loads((RES_DIR / "image_assets.json").read_text(encoding="utf-8"))
IMAGE_ASSETS: dict[str, tuple[str, str]] = {
    name: (source, path) for source, data in IMAGE_SOURCES.items() for name, path in data["files"].items()
}


def image_resource_url(name: str) -> str:
    """优先读取数据目录；尚未同步时使用同一上游图片。"""
    source, original_path = IMAGE_ASSETS[name]
    local_path = IMAGE_DIR / source / original_path
    if local_path.is_file():
        return local_path.as_uri()
    url = IMAGE_SOURCES[source]["base_url"] + quote(original_path, safe="/")
    if config.github_proxy_url and urlsplit(url).hostname == "raw.githubusercontent.com":
        url = f"{config.github_proxy_url.rstrip('/')}/{url}"
    return url
