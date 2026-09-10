"""隔离 htmlrender 0.8 与旧版的模板、页面和截图接口差异。"""

from pathlib import Path
from typing import Any, Literal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from playwright.async_api import Page
import nonebot_plugin_htmlrender as _htmlrender

if hasattr(_htmlrender, "get_new_page"):
    get_new_page = getattr(_htmlrender, "get_new_page")
    html_to_pic = getattr(_htmlrender, "html_to_pic")
    template_to_html = getattr(_htmlrender, "template_to_html")
    template_to_pic = getattr(_htmlrender, "template_to_pic")
else:
    from typing import cast
    from copy import deepcopy
    from collections.abc import Mapping

    from anyio import CancelScope
    from nonebot import get_driver
    from nonebot_plugin_htmlrender.capabilities import PLAYWRIGHT
    from nonebot_plugin_htmlrender.adapters.playwright.provider import PROVIDER
    from nonebot_plugin_htmlrender import Application, RenderTemplateHtmlRequest
    from nonebot_plugin_htmlrender.adapters.playwright.config import PlaywrightConfig
    from nonebot_plugin_htmlrender.bootstrap import prepare_runtime, load_render_settings
    from nonebot_plugin_htmlrender.preparation.materialize import materialize_local_assets
    from nonebot_plugin_htmlrender.adapters.playwright._page import install_filehost_request_route
    from nonebot_plugin_htmlrender.rendering.errors import CapabilityUnavailable, ProviderLifecycleError
    from nonebot_plugin_htmlrender.adapters.playwright.operations import (
        _publish_prepared_assets,
        _assert_no_local_resources,
    )
    from nonebot_plugin_htmlrender.adapters.playwright.prepared import (
        BrowserLoadPlan,
        build_browser_load_plan,
        install_browser_asset_routes,
    )
    from nonebot_plugin_htmlrender.resources.config import (
        ResourceStrategy,
        ResourceResolveMode,
        LocalLocalResourcePolicy,
        RemoteLocalResourcePolicy,
    )
    from nonebot_plugin_htmlrender.providers.sdk import (
        EngineBindings,
        EngineProvider,
        PluginRequirement,
        ProviderAvailability,
        ProviderDependencies,
    )

    from .config import RES_DIR, CACHE_DIR

    class _ScopedPlaywrightProvider:
        """从上游组合入口取得私有资源服务和发布器，不改写其实现或全局状态。"""

        id = "skland-playwright"

        def __init__(self, shared: Application | None) -> None:
            self.shared = shared
            self.dependencies: ProviderDependencies | None = None

        def parse_settings(self, raw: Mapping[str, object]) -> PlaywrightConfig:
            return PROVIDER.parse_settings(raw)

        def availability(self, settings: PlaywrightConfig) -> ProviderAvailability:
            return PROVIDER.availability(settings)

        def bootstrap_requirements(self, settings: PlaywrightConfig) -> tuple[PluginRequirement, ...]:
            return PROVIDER.bootstrap_requirements(settings)

        def resource_strategy(self, settings: PlaywrightConfig) -> ResourceStrategy:
            return self.shared.resources.strategy if self.shared is not None else PROVIDER.resource_strategy(settings)

        def compose(self, settings: PlaywrightConfig, dependencies: ProviderDependencies) -> EngineBindings:
            self.dependencies = dependencies
            return PROVIDER.compose(settings, dependencies)

    _application: Application | None = None
    _provider: _ScopedPlaywrightProvider | None = None
    _closed = False

    def _get_application() -> Application:
        global _application, _provider
        if _closed:
            raise ProviderLifecycleError("Skland renderer is closed.")
        if _application is None:
            settings = deepcopy(load_render_settings())
            shared = _htmlrender.get_default_application()
            _provider = _ScopedPlaywrightProvider(shared if shared.extensions.get(PLAYWRIGHT) is not None else None)
            # 只为本插件的模板扩展权限，不污染其他插件共用的 Application。
            settings.resources.local_access.allowed_paths = list(
                dict.fromkeys([*settings.resources.local_access.allowed_paths, RES_DIR, CACHE_DIR])
            )
            settings.graphics.backends = ()
            if settings.provider not in (None, "playwright"):
                settings.provider_config = {}
            settings.provider = _provider.id
            _application = prepare_runtime(
                settings, explicit_providers=(cast(EngineProvider[object], _provider),)
            ).build_application()
        return _application

    @get_driver().on_shutdown
    async def _close_application() -> None:
        global _closed
        _closed = True
        if _application is not None:
            await _application.aclose()

    @asynccontextmanager
    async def get_new_page(device_scale_factor: float = 2, **kwargs: Any) -> AsyncIterator[Page]:
        application = _get_application()
        playwright = _htmlrender.get_default_application().extensions.get(PLAYWRIGHT)
        if playwright is None:
            playwright = application.extensions.playwright
        async with playwright.page(device_scale_factor=device_scale_factor, **kwargs) as page:
            yield page

    async def template_to_html(
        template_path: str,
        template_name: str,
        filters: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        return str(
            await _get_application().renderer.render_template_html(
                RenderTemplateHtmlRequest(
                    template_path=template_path,
                    template_name=template_name,
                    variables=kwargs,
                    filters=filters,
                )
            )
        )

    @asynccontextmanager
    async def _prepare_page_resources(
        html: str, base_url: str
    ) -> AsyncIterator[tuple[BrowserLoadPlan, dict[str, Mapping[str, str]]]]:
        application = _get_application()
        if _provider is None or _provider.dependencies is None:
            raise CapabilityUnavailable("playwright")
        dependencies = _provider.dependencies
        strategy = dependencies.resources.strategy
        policy = strategy.remote_local_policy if strategy.is_remote else strategy.local_local_policy
        if strategy.resolve_mode is ResourceResolveMode.OFF:
            policy = RemoteLocalResourcePolicy.PASSTHROUGH
        prepared = await application.preparation.prepare_html(html, base_url=f"{base_url.rstrip('/')}/")
        asset_urls = None
        authorization: dict[str, Mapping[str, str]] = {}
        publisher = dependencies.asset_publisher
        lease_id = None
        try:
            if policy in (RemoteLocalResourcePolicy.MEMORY, RemoteLocalResourcePolicy.FILEHOST):
                prepared = await materialize_local_assets(
                    prepared,
                    resources=dependencies.resources,
                    strict=strategy.resolve_mode is ResourceResolveMode.STRICT,
                )
                if policy == RemoteLocalResourcePolicy.FILEHOST and prepared.assets:
                    if publisher is None:
                        raise CapabilityUnavailable("filehost")
                    lease_id = publisher.create_lease()
                    asset_urls, authorization = await _publish_prepared_assets(
                        prepared, publisher=publisher, lease_id=lease_id
                    )
            elif policy is RemoteLocalResourcePolicy.ERROR:
                _assert_no_local_resources(prepared, document_url=None)
            direct_files = policy in (LocalLocalResourcePolicy.FILE, RemoteLocalResourcePolicy.PASSTHROUGH)
            yield (
                build_browser_load_plan(
                    prepared,
                    document_url=base_url if direct_files else None,
                    asset_urls=asset_urls,
                    allow_file_base_href=direct_files,
                ),
                authorization,
            )
        finally:
            if lease_id is not None and publisher is not None:
                with CancelScope(shield=True):
                    await publisher.release(lease_id)

    async def html_to_pic(
        html: str,
        wait: int = 0,
        template_path: str | None = None,
        type: Literal["jpeg", "png"] = "png",
        quality: int | None = None,
        device_scale_factor: float = 2,
        screenshot_timeout: float | None = 30_000,
        **kwargs: Any,
    ) -> bytes:
        # 复用上游资源策略，但保留原生截图的全页、页面参数和毫秒超时契约。
        async with (
            _prepare_page_resources(html, template_path or Path.cwd().as_uri()) as (plan, authorization),
            get_new_page(device_scale_factor, **kwargs) as page,
        ):
            if authorization:
                await install_filehost_request_route(page, authorization=authorization)
            await install_browser_asset_routes(page, plan)
            if plan.document_url is not None:
                await page.goto(plan.document_url, wait_until="load")
            await page.set_content(plan.html, wait_until="networkidle")
            await page.wait_for_timeout(wait)
            return await page.screenshot(
                full_page=True,
                type=type,
                quality=quality,
                timeout=screenshot_timeout,
            )

    async def template_to_pic(
        template_path: str,
        template_name: str,
        templates: dict[str, Any],
        filters: dict[str, Any] | None = None,
        pages: dict[str, Any] | None = None,
        wait: int = 0,
        type: Literal["jpeg", "png"] = "png",
        quality: int | None = None,
        device_scale_factor: float = 2,
        screenshot_timeout: float | None = 30_000,
    ) -> bytes:
        html = await template_to_html(template_path, template_name, filters=filters, **templates)
        if pages is None:
            pages = {"viewport": {"width": 500, "height": 10}, "base_url": Path.cwd().as_uri()}
        return await html_to_pic(
            html=html,
            template_path=Path(template_path).resolve().as_uri(),
            wait=wait,
            type=type,
            quality=quality,
            device_scale_factor=device_scale_factor,
            screenshot_timeout=screenshot_timeout,
            **pages,
        )
