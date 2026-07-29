from __future__ import annotations

import os
import asyncio
from uuid import uuid4
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit
from contextvars import ContextVar
from collections.abc import Iterator
from contextlib import suppress, nullcontext, contextmanager

from nonebot import logger
from playwright.async_api import Page
from playwright.async_api import Request
from nonebot_plugin_htmlrender import template_to_html
from playwright.async_api import Error as PlaywrightError
from nonebot_plugin_htmlrender import html_to_pic, get_new_page
from nonebot_plugin_htmlrender import template_to_pic as base_template_to_pic

from .config import CACHE_DIR, config

PendingImage = tuple[str, Path]
PageReadiness = Literal["networkidle", "resources"]

_RESOURCE_READY_SCRIPT = """async () => {
  await document.fonts.ready;
  await Promise.all(
    Array.from(document.images, async image => {
      if (!image.complete) {
        await new Promise(resolve => {
          image.addEventListener("load", resolve, { once: true });
          image.addEventListener("error", resolve, { once: true });
        });
      }
      if (typeof image.decode === "function") {
        try {
          await image.decode();
        } catch {}
      }
    }),
  );
}"""

_IMAGE_DOWNLOAD_MAX_BYTES = 10 * 1024 * 1024
_ALLOWED_IMAGE_PATH_PREFIXES = (
    "/arknights/game/assets/char/portrait/",
    "/arknights/game/assets/char_skin/portrait/",
)
_pending_images: ContextVar[set[PendingImage] | None] = ContextVar("skland_pending_images", default=None)


def register_missing_image(url: str, path: Path) -> None:
    pending = _pending_images.get()
    if pending is not None and _is_allowed_image(url, path):
        pending.add((url, path))


@contextmanager
def _collect_missing_images() -> Iterator[set[PendingImage]]:
    pending: set[PendingImage] = set()
    token = _pending_images.set(pending)
    try:
        yield pending
    finally:
        _pending_images.reset(token)


async def _wait_for_page_resources(page: Page, timeout: float | None) -> None:
    waiter = page.evaluate(_RESOURCE_READY_SCRIPT)
    if timeout is None:
        await waiter
        return
    await asyncio.wait_for(waiter, timeout / 1000)


def _is_allowed_image(url: str, path: Path) -> bool:
    try:
        parsed_url = urlsplit(url)
        return (
            parsed_url.scheme == "https"
            and parsed_url.hostname == "web.hycdn.cn"
            and any(parsed_url.path.startswith(prefix) for prefix in _ALLOWED_IMAGE_PATH_PREFIXES)
            and path.resolve().is_relative_to(CACHE_DIR.resolve())
        )
    except (OSError, ValueError):
        return False


async def _cache_finished_request(request: Request, path: Path) -> None:
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        if path.exists():
            return

        response = await request.response()
        if response is None or not 200 <= response.status < 300:
            return

        content_type = response.headers.get("content-type", "").partition(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            return

        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > _IMAGE_DOWNLOAD_MAX_BYTES:
            return

        body = await response.body()
        if not body or len(body) > _IMAGE_DOWNLOAD_MAX_BYTES:
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_bytes(body)
        os.replace(temporary_path, path)
    except (OSError, ValueError, PlaywrightError) as e:
        logger.warning(f"Failed to cache render image {request.url}: {type(e).__name__}: {e}")
    finally:
        with suppress(OSError):
            temporary_path.unlink(missing_ok=True)


async def _html_to_pic_with_cache(
    *,
    html: str,
    pending: set[PendingImage],
    template_path: str,
    wait: int,
    type: Literal["jpeg", "png"],
    quality: int | None,
    device_scale_factor: float,
    screenshot_timeout: float | None,
    pages: dict[Any, Any],
    readiness: PageReadiness,
) -> bytes:
    pending_by_url = dict(pending)
    cache_tasks: list[asyncio.Task[None]] = []

    async with get_new_page(device_scale_factor, **pages) as page:
        page.on("console", lambda msg: logger.debug(f"Browser console: {msg.text}"))

        def cache_request(request: Request) -> None:
            path = pending_by_url.get(request.url)
            if path is not None:
                cache_tasks.append(asyncio.create_task(_cache_finished_request(request, path)))

        page.on("requestfinished", cache_request)
        await page.goto(template_path, wait_until="load")
        await page.set_content(html, wait_until="load" if readiness == "resources" else "networkidle")
        if readiness == "resources":
            await _wait_for_page_resources(page, screenshot_timeout)
        await page.wait_for_timeout(wait)
        screenshot = await page.screenshot(
            full_page=True,
            type=type,
            quality=quality,
            timeout=screenshot_timeout,
        )
        if cache_tasks:
            await asyncio.gather(*cache_tasks)
        return screenshot


async def cached_template_to_pic(
    template_path: str,
    template_name: str,
    templates: dict[Any, Any],
    filters: dict[str, Any] | None = None,
    pages: dict[Any, Any] | None = None,
    wait: int = 0,
    type: Literal["jpeg", "png"] = "png",
    quality: int | None = None,
    device_scale_factor: float = 2,
    screenshot_timeout: float | None = 30_000,
    readiness: PageReadiness = "networkidle",
) -> bytes:
    if not config.ark_portrait_cache_enabled and readiness == "networkidle":
        return await base_template_to_pic(
            template_path=template_path,
            template_name=template_name,
            templates=templates,
            filters=filters,
            pages=pages,
            wait=wait,
            type=type,
            quality=quality,
            device_scale_factor=device_scale_factor,
            screenshot_timeout=screenshot_timeout,
        )

    empty_pending: set[PendingImage] = set()
    collector = _collect_missing_images() if config.ark_portrait_cache_enabled else nullcontext(empty_pending)
    with collector as pending:
        html = await template_to_html(
            template_path=template_path,
            template_name=template_name,
            filters=filters,
            **templates,
        )

    if pages is None:
        pages = {
            "viewport": {"width": 500, "height": 10},
            "base_url": f"file://{os.getcwd()}",
        }

    html_template_path = f"file://{template_path}"
    requires_custom_renderer = bool(pending) or readiness == "resources"
    if requires_custom_renderer:
        return await _html_to_pic_with_cache(
            html=html,
            pending=pending,
            template_path=html_template_path,
            wait=wait,
            type=type,
            quality=quality,
            device_scale_factor=device_scale_factor,
            screenshot_timeout=screenshot_timeout,
            pages=pages,
            readiness=readiness,
        )

    return await html_to_pic(
        html=html,
        template_path=html_template_path,
        wait=wait,
        type=type,
        quality=quality,
        device_scale_factor=device_scale_factor,
        screenshot_timeout=screenshot_timeout,
        **pages,
    )
