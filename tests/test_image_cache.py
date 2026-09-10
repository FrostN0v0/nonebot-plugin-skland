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
    def __init__(self, requests: list[FakeRequest], image: bytes) -> None:
        self.requests = requests
        self.image = image
        self.handlers: dict[str, list[Any]] = {}
        self.html = ""

    def on(self, event: str, handler: Any) -> None:
        self.handlers.setdefault(event, []).append(handler)

    async def goto(self, url: str, *, wait_until: str | None = None) -> None:
        return None

    async def set_content(self, html: str, *, wait_until: str) -> None:
        self.html = html
        for request in self.requests:
            for handler in self.handlers.get("requestfinished", []):
                handler(request)

    async def wait_for_timeout(self, timeout: int) -> None:
        return None

    async def evaluate(self, script: str) -> None:
        return None

    async def screenshot(self, **kwargs: Any) -> bytes:
        return self.image


def fake_page_context(page: FakePage):
    @asynccontextmanager
    async def get_page(*args: Any, **kwargs: Any) -> AsyncIterator[FakePage]:
        yield page

    return get_page


@pytest.mark.asyncio
async def test_cached_template_uses_remote_portraits_then_local_files(app, tmp_path, mocker, monkeypatch, tiny_png):
    from nonebot_plugin_skland.config import config
    from nonebot_plugin_skland import filters, image_cache

    monkeypatch.setattr(config, "ark_portrait_cache_enabled", True)
    monkeypatch.setattr(filters, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(image_cache, "CACHE_DIR", tmp_path)

    template_path = tmp_path / "templates"
    template_path.mkdir()
    template_name = "portraits.html.jinja2"
    (template_path / template_name).write_text(
        '<img src="{{ skin_id | skin_portrait }}"><img src="{{ char_id | character_portrait }}">',
        encoding="utf-8",
    )

    skin_id = "char_290_vigna@summer#1"
    char_id = "char_290_vigna"
    skin_url = "https://web.hycdn.cn/arknights/game/assets/char_skin/portrait/char_290_vigna%40summer%231.png"
    char_url = "https://web.hycdn.cn/arknights/game/assets/char/portrait/char_290_vigna.png"
    skin_path = tmp_path / "portrait" / "char_290_vigna_summer#1.png"
    char_path = tmp_path / "portrait" / "char_290_vigna.png"
    page = FakePage(
        [FakeRequest(skin_url, FakeResponse(tiny_png)), FakeRequest(char_url, FakeResponse(tiny_png))],
        tiny_png,
    )
    monkeypatch.setattr(image_cache, "get_new_page", fake_page_context(page))
    local_renderer = mocker.patch.object(image_cache, "html_to_pic", new=mocker.AsyncMock(return_value=tiny_png))

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

    assert first == tiny_png
    assert skin_url in page.html
    assert char_url in page.html
    assert skin_path.read_bytes() == tiny_png
    assert char_path.read_bytes() == tiny_png

    second = await image_cache.cached_template_to_pic(**render_kwargs)

    assert second == tiny_png
    local_html = local_renderer.await_args.kwargs["html"]
    assert skin_path.as_uri() in local_html
    assert char_path.as_uri() in local_html
    assert skin_url not in local_html
    assert char_url not in local_html


@pytest.mark.asyncio
async def test_cached_template_leaves_unknown_urls_untouched(app, tmp_path, mocker, monkeypatch, tiny_png):
    from nonebot_plugin_skland import image_cache
    from nonebot_plugin_skland.config import config

    monkeypatch.setattr(config, "ark_portrait_cache_enabled", True)
    template_path = tmp_path / "templates"
    template_path.mkdir()
    template_name = "remote.html.jinja2"
    (template_path / template_name).write_text('<img src="{{ image_url }}">', encoding="utf-8")

    renderer = mocker.patch.object(image_cache, "html_to_pic", new=mocker.AsyncMock(return_value=tiny_png))
    remote_url = "https://example.com/api-returned-image.png"

    await image_cache.cached_template_to_pic(
        template_path=str(template_path),
        template_name=template_name,
        templates={"image_url": remote_url},
    )

    assert remote_url in renderer.await_args.kwargs["html"]


@pytest.mark.parametrize(
    ("status", "content_type"),
    [(404, "image/png"), (200, "text/html")],
)
@pytest.mark.asyncio
async def test_cached_template_skips_failed_portrait_responses(
    app, tmp_path, monkeypatch, tiny_png, status, content_type
):
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
    page = FakePage(
        [FakeRequest(skin_url, FakeResponse(b"not-an-image", status=status, content_type=content_type))],
        tiny_png,
    )
    monkeypatch.setattr(image_cache, "get_new_page", fake_page_context(page))

    result = await image_cache.cached_template_to_pic(
        template_path=str(template_path),
        template_name=template_name,
        templates={"skin_id": skin_id},
        filters={"portrait_url": filters.ark_skin_portrait_url},
    )

    assert result == tiny_png
    assert skin_url in page.html
    assert not skin_path.exists()


@pytest.mark.asyncio
async def test_disabled_cache_keeps_portraits_remote_without_writing_files(app, tmp_path, monkeypatch, tiny_png):
    from nonebot_plugin_skland.config import config
    from nonebot_plugin_skland import filters, image_cache

    monkeypatch.setattr(config, "ark_portrait_cache_enabled", False)
    monkeypatch.setattr(filters, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(image_cache, "CACHE_DIR", tmp_path)
    template = tmp_path / "portrait.html.jinja2"
    template.write_text('<img src="{{ skin_id | portrait_url }}">', encoding="utf-8")
    skin_url = "https://web.hycdn.cn/arknights/game/assets/char_skin/portrait/char_290_vigna%40summer%231.png"
    page = FakePage([FakeRequest(skin_url, FakeResponse(tiny_png))], tiny_png)
    monkeypatch.setattr(image_cache, "get_new_page", fake_page_context(page))

    await image_cache.cached_template_to_pic(
        template_path=str(tmp_path),
        template_name=template.name,
        templates={"skin_id": "char_290_vigna@summer#1"},
        filters={"portrait_url": filters.ark_skin_portrait_url},
        readiness="resources",
    )

    assert skin_url in page.html
    assert not (tmp_path / "portrait").exists()


@pytest.mark.asyncio
async def test_cached_template_waits_until_resources_are_ready(app, tmp_path, monkeypatch, tiny_png):
    from nonebot_plugin_skland import image_cache
    from nonebot_plugin_skland.config import config

    monkeypatch.setattr(config, "ark_portrait_cache_enabled", False)
    template = tmp_path / "resources.html.jinja2"
    template.write_text("<p>Resource readiness</p>", encoding="utf-8")
    waiting = asyncio.Event()
    ready = asyncio.Event()

    class LoadingPage(FakePage):
        async def evaluate(self, script: str) -> None:
            waiting.set()
            await ready.wait()

        async def screenshot(self, **kwargs: Any) -> bytes:
            assert ready.is_set(), "A screenshot must not precede resource readiness"
            return await super().screenshot(**kwargs)

    page = LoadingPage([], tiny_png)
    monkeypatch.setattr(image_cache, "get_new_page", fake_page_context(page))
    rendering = asyncio.create_task(
        image_cache.cached_template_to_pic(
            template_path=str(tmp_path),
            template_name=template.name,
            templates={},
            readiness="resources",
        )
    )
    try:
        await asyncio.wait_for(waiting.wait(), 1)
        assert not rendering.done()
        ready.set()
        assert await rendering == tiny_png
    finally:
        rendering.cancel()
        await asyncio.gather(rendering, return_exceptions=True)


@pytest.mark.asyncio
async def test_page_resource_wait_respects_timeout(app):
    from nonebot_plugin_skland.image_cache import wait_for_page_resources

    class SlowPage:
        async def evaluate(self, script: str) -> None:
            await asyncio.Event().wait()

    with pytest.raises(asyncio.TimeoutError):
        await wait_for_page_resources(SlowPage(), 1)
