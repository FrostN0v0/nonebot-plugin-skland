from __future__ import annotations

import asyncio
from typing import Any
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        *,
        status: int = 200,
        content_type: str = "image/png",
    ) -> None:
        self.status = status
        self.headers = {
            "content-type": content_type,
            "content-length": str(len(body)),
        }
        self._body = body

    async def body(self) -> bytes:
        return self._body


class FakeRequest:
    def __init__(self, url: str, response: FakeResponse) -> None:
        self.url = url
        self._response = response

    async def response(self) -> FakeResponse:
        return self._response


class FakePage:
    def __init__(self, requests: list[FakeRequest]) -> None:
        self.requests = requests
        self.handlers: dict[str, list[Any]] = {}
        self.html = ""
        self.goto_wait_until: str | None = None
        self.wait_until = ""
        self.evaluated_scripts: list[str] = []

    def on(self, event: str, handler: Any) -> None:
        self.handlers.setdefault(event, []).append(handler)

    async def goto(self, url: str, *, wait_until: str | None = None) -> None:
        self.goto_wait_until = wait_until
        return None

    async def set_content(self, html: str, *, wait_until: str) -> None:
        self.html = html
        self.wait_until = wait_until
        for request in self.requests:
            for handler in self.handlers.get("requestfinished", []):
                handler(request)

    async def wait_for_timeout(self, timeout: int) -> None:
        return None

    async def evaluate(self, script: str) -> None:
        self.evaluated_scripts.append(script)

    async def screenshot(self, **kwargs: Any) -> bytes:
        return b"image"


def fake_page_context(page: FakePage):
    @asynccontextmanager
    async def get_page(*args: Any, **kwargs: Any) -> AsyncIterator[FakePage]:
        yield page

    return get_page


@pytest.mark.asyncio
async def test_cached_template_saves_browser_portrait_responses_without_rerender(app, tmp_path, mocker, monkeypatch):
    from nonebot_plugin_skland.config import config
    from nonebot_plugin_skland import filters, image_cache

    monkeypatch.setattr(config, "ark_portrait_cache_enabled", True)
    monkeypatch.setattr(filters, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(image_cache, "CACHE_DIR", tmp_path)

    template_path = tmp_path / "templates"
    template_path.mkdir()
    template_name = "portraits.html.jinja2"
    (template_path / template_name).write_text(
        """
        <img src="{{ skin_id | skin_portrait }}">
        <img src="{{ char_id | character_portrait }}">
        """,
        encoding="utf-8",
    )

    skin_id = "char_290_vigna@summer#1"
    char_id = "char_290_vigna"
    skin_url = "https://web.hycdn.cn/arknights/game/assets/char_skin/portrait/char_290_vigna%40summer%231.png"
    char_url = "https://web.hycdn.cn/arknights/game/assets/char/portrait/char_290_vigna.png"
    skin_path = tmp_path / "portrait" / "char_290_vigna_summer#1.png"
    char_path = tmp_path / "portrait" / "char_290_vigna.png"
    page = FakePage(
        [
            FakeRequest(skin_url, FakeResponse(b"skin-image")),
            FakeRequest(char_url, FakeResponse(b"character-image")),
        ]
    )
    monkeypatch.setattr(image_cache, "get_new_page", fake_page_context(page))
    template_renderer = mocker.patch.object(
        image_cache,
        "template_to_html",
        new=mocker.AsyncMock(wraps=image_cache.template_to_html),
    )
    local_renderer = mocker.patch.object(
        image_cache,
        "html_to_pic",
        new=mocker.AsyncMock(return_value=b"local-image"),
    )

    render_kwargs = {
        "template_path": str(template_path),
        "template_name": template_name,
        "templates": {"skin_id": skin_id, "char_id": char_id},
        "filters": {
            "skin_portrait": filters.ark_skin_portrait_url,
            "character_portrait": filters.charId_to_portraitUrl,
        },
    }
    first = await image_cache.cached_template_to_pic(**render_kwargs)

    assert first == b"image"
    assert template_renderer.await_count == 1
    assert skin_url in page.html
    assert char_url in page.html
    assert skin_path.read_bytes() == b"skin-image"
    assert char_path.read_bytes() == b"character-image"
    local_renderer.assert_not_awaited()

    second = await image_cache.cached_template_to_pic(**render_kwargs)

    assert second == b"local-image"
    assert template_renderer.await_count == 2
    assert skin_path.as_uri() in local_renderer.await_args.kwargs["html"]
    assert char_path.as_uri() in local_renderer.await_args.kwargs["html"]


@pytest.mark.asyncio
async def test_cached_template_leaves_unknown_urls_untouched(app, tmp_path, mocker, monkeypatch):
    from nonebot_plugin_skland import image_cache
    from nonebot_plugin_skland.config import config

    monkeypatch.setattr(config, "ark_portrait_cache_enabled", True)
    template_path = tmp_path / "templates"
    template_path.mkdir()
    template_name = "remote.html.jinja2"
    (template_path / template_name).write_text('<img src="{{ image_url }}">', encoding="utf-8")

    renderer = mocker.patch.object(
        image_cache,
        "html_to_pic",
        new=mocker.AsyncMock(return_value=b"image"),
    )
    remote_url = "https://example.com/api-returned-image.png"

    result = await image_cache.cached_template_to_pic(
        template_path=str(template_path),
        template_name=template_name,
        templates={"image_url": remote_url},
    )

    assert result == b"image"
    assert remote_url in renderer.await_args.kwargs["html"]


@pytest.mark.asyncio
async def test_cached_template_skips_failed_portrait_responses(app, tmp_path, mocker, monkeypatch):
    from nonebot_plugin_skland.config import config
    from nonebot_plugin_skland import filters, image_cache

    monkeypatch.setattr(config, "ark_portrait_cache_enabled", True)
    monkeypatch.setattr(filters, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(image_cache, "CACHE_DIR", tmp_path)

    template_path = tmp_path / "templates"
    template_path.mkdir()
    template_name = "portrait.html.jinja2"
    (template_path / template_name).write_text('<img src="{{ skin_id | portrait_url }}">', encoding="utf-8")

    skin_id = "char_290_vigna@summer#1"
    skin_url = "https://web.hycdn.cn/arknights/game/assets/char_skin/portrait/char_290_vigna%40summer%231.png"
    skin_path = tmp_path / "portrait" / "char_290_vigna_summer#1.png"
    page = FakePage([FakeRequest(skin_url, FakeResponse(b"not-found", status=404))])
    monkeypatch.setattr(image_cache, "get_new_page", fake_page_context(page))

    result = await image_cache.cached_template_to_pic(
        template_path=str(template_path),
        template_name=template_name,
        templates={"skin_id": skin_id},
        filters={"portrait_url": filters.ark_skin_portrait_url},
    )

    assert result == b"image"
    assert skin_url in page.html
    assert not skin_path.exists()


@pytest.mark.asyncio
async def test_cached_template_delegates_when_disabled(app, mocker, monkeypatch):
    from nonebot_plugin_skland import image_cache
    from nonebot_plugin_skland.config import config

    monkeypatch.setattr(config, "ark_portrait_cache_enabled", False)
    renderer = mocker.patch.object(
        image_cache,
        "base_template_to_pic",
        new=mocker.AsyncMock(return_value=b"image"),
    )
    template_renderer = mocker.patch.object(
        image_cache,
        "template_to_html",
        new=mocker.AsyncMock(),
    )

    result = await image_cache.cached_template_to_pic(
        template_path="templates",
        template_name="card.html.jinja2",
        templates={"value": 1},
    )

    assert result == b"image"
    renderer.assert_awaited_once()
    assert renderer.await_args.kwargs["screenshot_timeout"] == 30_000
    template_renderer.assert_not_awaited()


@pytest.mark.asyncio
async def test_cached_template_waits_for_page_resources_when_requested(app, tmp_path, mocker, monkeypatch):
    from nonebot_plugin_skland import image_cache
    from nonebot_plugin_skland.config import config

    monkeypatch.setattr(config, "ark_portrait_cache_enabled", False)
    template_path = tmp_path / "templates"
    template_path.mkdir()
    template_name = "resources.html.jinja2"
    (template_path / template_name).write_text('<img src="data:image/png;base64,AA==">', encoding="utf-8")
    page = FakePage([])
    monkeypatch.setattr(image_cache, "get_new_page", fake_page_context(page))
    base_renderer = mocker.patch.object(
        image_cache,
        "base_template_to_pic",
        new=mocker.AsyncMock(return_value=b"base-image"),
    )

    result = await image_cache.cached_template_to_pic(
        template_path=str(template_path),
        template_name=template_name,
        templates={},
        readiness="resources",
    )

    assert result == b"image"
    base_renderer.assert_not_awaited()
    assert page.goto_wait_until == "load"
    assert page.wait_until == "load"
    assert len(page.evaluated_scripts) == 1
    assert "document.fonts.ready" in page.evaluated_scripts[0]
    assert "image.decode" in page.evaluated_scripts[0]


@pytest.mark.asyncio
async def test_page_resource_wait_respects_timeout(app):
    from nonebot_plugin_skland.image_cache import _wait_for_page_resources

    class SlowPage:
        async def evaluate(self, script: str) -> None:
            await asyncio.sleep(0.05)

    with pytest.raises(asyncio.TimeoutError):
        await _wait_for_page_resources(SlowPage(), 1)


def test_ark_portrait_cache_config(app):
    from nonebot_plugin_skland.config import ScopedConfig

    assert ScopedConfig().ark_portrait_cache_enabled is False
    assert ScopedConfig(ark_portrait_cache_enabled=True).ark_portrait_cache_enabled is True
