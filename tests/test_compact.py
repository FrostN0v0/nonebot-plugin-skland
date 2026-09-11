"""Compatibility rendering and lifecycle behavior across supported htmlrender versions."""

from copy import deepcopy
from contextlib import asynccontextmanager

import pytest
import nonebot


@asynccontextmanager
async def _serve_asgi(application):
    import socket
    import asyncio

    import uvicorn

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(application, lifespan="off", log_level="critical", access_log=False))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            while not server.started:
                if serving.done():
                    await serving
                    raise RuntimeError("Fixture HTTP server exited before startup")
                await asyncio.sleep(0.01)
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            await asyncio.wait_for(serving, 10)


@pytest.fixture(autouse=True)
async def isolated_compact_application(app, monkeypatch):
    from nonebot_plugin_skland import compact

    close_application = getattr(compact, "_close_application", None)
    if close_application is None:
        yield
        return

    driver = nonebot.get_driver()
    original_render = driver.config.render
    monkeypatch.setattr(compact, "_application", None)
    monkeypatch.setattr(compact, "_provider", None)
    monkeypatch.setattr(compact, "_closed", False)
    try:
        yield
    finally:
        try:
            await close_application()
        finally:
            setattr(driver.config, "render", original_render)


@pytest.fixture
def htmlrender_08(app):
    import nonebot_plugin_htmlrender as htmlrender

    if not hasattr(htmlrender, "get_default_application"):
        pytest.skip("Scoped Application resources require htmlrender 0.8")
    return htmlrender


@pytest.fixture
async def remote_browser(htmlrender_08, tmp_path):
    from playwright.async_api import Error, async_playwright

    profile = tmp_path / "browser-profile"
    async with async_playwright() as playwright:
        try:
            context = await playwright.chromium.launch_persistent_context(
                str(profile), channel="chromium", headless=True, args=["--remote-debugging-port=0"]
            )
        except Error as error:
            if "Executable doesn't exist" in str(error):
                pytest.skip("This regression requires an installed Chromium; it never installs a browser")
            raise
        try:
            port = (profile / "DevToolsActivePort").read_text(encoding="utf-8").splitlines()[0]
            yield f"http://127.0.0.1:{port}"
        finally:
            await context.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("release", "expected"),
    [("0.6.5", False), ("0.7.7", False), ("0.8.0", True), ("1.0.0", True)],
)
async def test_htmlrender_version_gate_prefers_distribution_metadata(app, monkeypatch, release, expected):
    from nonebot_plugin_skland import compact

    monkeypatch.setattr(compact, "version", lambda _: release)
    monkeypatch.delattr(compact._htmlrender, "get_default_application", raising=False)

    assert compact._uses_application_api() is expected


@pytest.mark.asyncio
@pytest.mark.parametrize("application_api_available", [False, True])
async def test_htmlrender_version_gate_falls_back_to_module_capability(app, monkeypatch, application_api_available):
    from importlib.metadata import PackageNotFoundError

    from nonebot_plugin_skland import compact

    def unavailable(_: str) -> str:
        raise PackageNotFoundError("nonebot-plugin-htmlrender")

    monkeypatch.setattr(compact, "version", unavailable)
    if application_api_available:
        monkeypatch.setattr(compact._htmlrender, "get_default_application", object(), raising=False)
    else:
        monkeypatch.delattr(compact._htmlrender, "get_default_application", raising=False)

    assert compact._uses_application_api() is application_api_available


@pytest.mark.asyncio
async def test_template_variables_do_not_become_renderer_options(app, tmp_path):
    from nonebot_plugin_skland.compact import template_to_html

    template = tmp_path / "variables.html.jinja2"
    template.write_text("{{ variables }}|{{ extensions }}|{{ value | shout }}", encoding="utf-8")

    html = await template_to_html(
        template_path=str(tmp_path),
        template_name=template.name,
        filters={"shout": str.upper},
        variables="template-data",
        extensions="not-a-jinja-extension",
        value="value",
    )

    assert html == "template-data|not-a-jinja-extension|VALUE"


@pytest.mark.asyncio
async def test_template_failure_preserves_the_original_error(app, tmp_path):
    import nonebot_plugin_htmlrender as htmlrender

    from nonebot_plugin_skland.compact import template_to_html

    template = tmp_path / "invalid.html.jinja2"
    template.write_text("{{ 1 / divisor }}", encoding="utf-8")

    error_type = getattr(htmlrender, "RenderingError", ZeroDivisionError)
    with pytest.raises(error_type) as failure:
        await template_to_html(
            template_path=str(tmp_path),
            template_name=template.name,
            divisor=0,
        )

    # 0.8 wraps Jinja errors; older versions expose the original exception directly.
    cause = failure.value
    while cause.__cause__ is not None:
        cause = cause.__cause__
    assert isinstance(cause, ZeroDivisionError)


@pytest.mark.asyncio
async def test_local_background_paths_are_preserved_for_messages(app, tmp_path, monkeypatch):
    from pathlib import Path

    from nonebot_plugin_alconna import Text, Image

    from nonebot_plugin_skland.config import CustomSource, config
    from nonebot_plugin_skland.utils.message import build_background_argot_segment
    from nonebot_plugin_skland.utils.background import (
        background_to_uri,
        get_background_image,
        get_rogue_background_image,
    )

    monkeypatch.setattr(config, "background_source", "default")
    monkeypatch.setattr(config, "rogue_background_source", "rogue")
    backgrounds = (
        await get_background_image("ark"),
        await get_background_image("endfield"),
        await get_rogue_background_image("rogue_1"),
    )
    assert all(isinstance(background, Path) for background in backgrounds)
    for background in backgrounds:
        assert isinstance(background, Path)
        assert background.is_file()
        assert background_to_uri(background) == background.as_uri()
        segment = build_background_argot_segment(background)
        assert isinstance(segment, Image)
        assert segment.path == background

    custom_background = tmp_path / "background #1.png"
    custom_background.write_bytes(b"image")
    assert CustomSource(uri=custom_background).resolve() == custom_background.resolve()

    remote_segments = build_background_argot_segment("https://example.com/background.png")
    assert isinstance(remote_segments, list)
    assert isinstance(remote_segments[0], Text)
    assert remote_segments[0].text == "https://example.com/background.png"
    assert isinstance(remote_segments[1], Image)
    assert remote_segments[1].url == "https://example.com/background.png"


@pytest.mark.asyncio
async def test_builtin_template_resources_are_private_with_zero_configuration(htmlrender_08, tmp_path):
    from nonebot_plugin_htmlrender.resources import ResourceAccessDenied

    from nonebot_plugin_skland import compact
    from nonebot_plugin_skland.config import RES_DIR
    from nonebot_plugin_skland.schemas import BoundRolesCard, BoundRoleCardItem, BoundRoleCardAccount

    shared = htmlrender_08.get_default_application()
    render_config = {}
    setattr(nonebot.get_driver().config, "render", render_config)
    original_config = deepcopy(render_config)
    template_path = RES_DIR / "templates"
    template_name = "bound_roles.html.jinja2"
    role = BoundRoleCardItem(
        app_code="arknights",
        app_name="明日方舟",
        nickname="自动授权 <Doctor>",
        binding_uid="12345678",
        game_role_id="internal-role",
        server_id="1",
        server_name="官服",
        level=None,
        is_skland_default=False,
        is_available=True,
        unavailable_reason=None,
        index=1,
        is_local_default=True,
    )
    props = BoundRolesCard(
        mode="overview",
        accounts=[
            BoundRoleCardAccount(
                account_id=1,
                index=1,
                account_user_id="internal-account",
                account_hint="",
                state="bound",
                roles=[role],
            )
        ],
    )

    with pytest.raises(ResourceAccessDenied):
        await htmlrender_08.render_template_html(
            template_path=template_path,
            template_name=template_name,
            variables={"props": props},
        )

    html = await compact.template_to_html(str(template_path), template_name, props=props)

    assert "自动授权 &lt;Doctor&gt;" in html
    assert role.player_uid in html
    assert role.game_role_id not in html
    assert nonebot.get_driver().config.render == original_config
    assert htmlrender_08.get_default_application() is shared
    with pytest.raises(ResourceAccessDenied):
        await htmlrender_08.render_template_html(
            template_path=template_path,
            template_name=template_name,
            variables={"props": props},
        )

    untrusted = tmp_path / "untrusted.html.jinja2"
    untrusted.write_text("untrusted template", encoding="utf-8")
    with pytest.raises(ResourceAccessDenied):
        await compact.template_to_html(str(tmp_path), untrusted.name)

    await compact._close_application()
    assert htmlrender_08.get_default_application() is shared
    # The fixture authorizes temporary templates only in the shared application.
    # A successful render after private teardown proves its lifetime is intact.
    assert (
        str(await htmlrender_08.render_template_html(template_path=tmp_path, template_name=untrusted.name))
        == "untrusted template"
    )


@pytest.mark.asyncio
async def test_private_resources_preserve_custom_template_authorization(htmlrender_08, tmp_path):
    from nonebot_plugin_htmlrender.resources import ResourceAccessDenied

    from nonebot_plugin_skland import compact

    shared = htmlrender_08.get_default_application()
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    template = custom_dir / "custom.html.jinja2"
    template.write_text("{% include 'fragment.html.jinja2' %}", encoding="utf-8")
    (custom_dir / "fragment.html.jinja2").write_text("custom {{ value }}", encoding="utf-8")
    render_config = {"resources": {"local_access": {"allowed_paths": [custom_dir]}}}
    original_config = deepcopy(render_config)
    setattr(nonebot.get_driver().config, "render", render_config)

    assert await compact.template_to_html(str(custom_dir), template.name, value="authorized") == "custom authorized"
    assert nonebot.get_driver().config.render == original_config
    assert htmlrender_08.get_default_application() is shared

    sibling_dir = tmp_path / "custom-other"
    sibling_dir.mkdir()
    (sibling_dir / template.name).write_text("outside custom authorization", encoding="utf-8")
    with pytest.raises(ResourceAccessDenied):
        await compact.template_to_html(str(sibling_dir), template.name)

    await compact._close_application()
    assert htmlrender_08.get_default_application() is shared
    assert (
        str(
            await htmlrender_08.render_template_html(
                template_path=custom_dir,
                template_name=template.name,
                variables={"value": "still open"},
            )
        )
        == "custom still open"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("initialized", [False, True])
async def test_shutdown_rejects_late_render_requests(htmlrender_08, tmp_path, initialized):
    from nonebot_plugin_htmlrender.rendering.errors import ProviderLifecycleError

    from nonebot_plugin_skland import compact

    template = tmp_path / "shutdown.html.jinja2"
    template.write_text("before shutdown", encoding="utf-8")
    if initialized:
        assert await compact.template_to_html(str(tmp_path), template.name) == "before shutdown"

    await compact._close_application()

    with pytest.raises(ProviderLifecycleError):
        await compact.template_to_html(str(tmp_path), template.name)
    with pytest.raises(ProviderLifecycleError):
        await compact.html_to_pic("<p>late screenshot</p>")
    with pytest.raises(ProviderLifecycleError):
        async with compact.open_html_page("<p>late page</p>"):
            pytest.fail("Shutdown must reject a new prepared page")
    with pytest.raises(ProviderLifecycleError):
        async with compact.get_new_page():
            pytest.fail("Shutdown must reject a new browser page")


@pytest.mark.asyncio
async def test_remote_error_policy_rejects_before_browser_access(htmlrender_08, tmp_path, monkeypatch):
    from nonebot_plugin_htmlrender.preparation.materialize import AssetMaterializationError

    from nonebot_plugin_skland import compact

    setattr(
        nonebot.get_driver().config,
        "render",
        {
            "provider": "playwright",
            "provider_config": {
                "connect_cdp": {"endpoint": "http://127.0.0.1:1"},
                "remote_local_resource_policy": "error",
            },
            "resources": {"local_access": {"allowed_paths": [tmp_path]}},
        },
    )

    @asynccontextmanager
    async def forbidden_browser(*args, **kwargs):
        pytest.fail("Rejected local resources must not reach the browser")
        yield

    monkeypatch.setattr(compact, "get_new_page", forbidden_browser)
    with pytest.raises(AssetMaterializationError):
        await compact.html_to_pic(
            '<style>body{background-image:url("fixture.png")}</style>', template_path=tmp_path.as_uri()
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(("policy", "shared"), [("memory", False), ("memory", True), ("filehost", True)])
@pytest.mark.parametrize("surface", ["html_to_pic", "open_html_page"])
async def test_remote_resources_render_without_browser_filesystem(
    htmlrender_08, tmp_path, monkeypatch, remote_browser, policy, shared, surface
):
    from io import BytesIO
    from contextlib import AsyncExitStack

    from PIL import Image
    from fastapi import FastAPI, Request, Response
    from nonebot_plugin_htmlrender.resources import ResourceAccessDenied
    from nonebot_plugin_htmlrender.api._default import set_default_application
    from nonebot_plugin_htmlrender.rendering.errors import ProviderLifecycleError
    from nonebot_plugin_htmlrender.adapters.resources import install_hosted_asset_store
    from nonebot_plugin_htmlrender.bootstrap import prepare_runtime, load_render_settings

    from nonebot_plugin_skland import compact
    from nonebot_plugin_skland.config import RES_DIR

    assets = tmp_path / "assets"
    (assets / "nested").mkdir(parents=True)
    picture = assets / "fixture.png"
    Image.new("RGB", (80, 80), (220, 30, 40)).save(picture)
    (assets / "fixture.otf").write_bytes((RES_DIR / "fonts" / "Bender.otf").read_bytes())
    (assets / "main.css").write_text('@import "nested/theme.css";', encoding="utf-8")
    (assets / "nested" / "theme.css").write_text(
        '@font-face{font-family:fixture;src:url("../fixture.otf")} '
        "body{margin:0;background:rgb(31,41,51)} "
        '.image{height:80px;width:80px;background-image:url("../fixture.png")} '
        ".tail{height:160px} .label{position:absolute;top:100px;font-family:fixture}",
        encoding="utf-8",
    )
    driver = nonebot.get_driver()
    setattr(
        driver.config,
        "render",
        {
            "provider": "playwright",
            "provider_config": {
                "connect_cdp": {"endpoint": remote_browser},
                "remote_local_resource_policy": policy,
                "resource_resolve_mode": "strict",
            },
            "resources": {"local_access": {"allowed_paths": [assets]}},
        },
    )
    original_application = htmlrender_08.get_default_application()
    shared_application = None
    hosted_store = None
    outside_headers = []
    font_states = []
    original_page = compact.get_new_page

    @asynccontextmanager
    async def remote_page(*args, **kwargs):
        async with original_page(*args, **kwargs) as page:
            connection = await page.context.new_cdp_session(page)
            await connection.send("Network.enable")
            await connection.send("Network.setBlockedURLs", {"urls": ["file://*"]})
            yield page
            font_states.extend(await page.evaluate("[...document.fonts].map(font => [font.family, font.status])"))

    monkeypatch.setattr(compact, "get_new_page", remote_page)
    async with AsyncExitStack() as stack:
        outside_image = ""
        if policy == "filehost":
            asgi = FastAPI()

            async def unrelated(request: Request):
                outside_headers.append(request.headers.get("X-HTMLRender-Filehost-Request"))
                return Response(picture.read_bytes(), media_type="image/png")

            asgi.add_api_route("/unrelated.png", unrelated)
            monkeypatch.setattr(driver, "_server_app", asgi)
            monkeypatch.setattr(driver._lifespan, "_shutdown_funcs", driver._lifespan._shutdown_funcs.copy())
            base_url = await stack.enter_async_context(_serve_asgi(asgi))
            driver.config.render["resources"]["filehost"] = {
                "public_base_url": f"{base_url}/_htmlrender/assets/",
                "request_header_value": "fixture-guard",
            }
            publisher_settings = prepare_runtime(load_render_settings()).asset_publisher_settings
            assert publisher_settings is not None
            hosted_store = install_hosted_asset_store(publisher_settings)
            assert hosted_store is not None
            outside_image = (
                f'<img src="{base_url}/unrelated.png" style="position:absolute;top:0;left:159px;width:1px;height:1px">'
            )

        try:
            if shared:
                settings = load_render_settings()
                settings.resources.local_access.allowed_paths = []
                shared_application = prepare_runtime(settings).build_application()
                set_default_application(shared_application)
            html = (
                '<link rel="stylesheet" href="main.css">'
                '<svg style="position:absolute;width:0;height:0"><filter id="fixture-filter">'
                "<feComponentTransfer/></filter></svg>"
                "<div style=\"display:none;filter:url('#fixture-filter')\"></div>"
                '<div class="image"></div><div class="tail"></div><span class="label">Fixture</span>' + outside_image
            )
            if surface == "html_to_pic":
                result = await compact.html_to_pic(
                    html,
                    template_path=assets.as_uri(),
                    viewport={"width": 160, "height": 10},
                    device_scale_factor=1.5,
                    screenshot_timeout=45_000,
                )
            else:
                async with compact.open_html_page(
                    html,
                    template_path=assets.as_uri(),
                    viewport={"width": 160, "height": 10},
                    device_scale_factor=1.5,
                ) as page:
                    result = await page.screenshot(full_page=True, type="png", timeout=45_000)
            with Image.open(BytesIO(result)) as rendered:
                assert rendered.format == "PNG"
                assert rendered.size == (240, 360)
                pixels = rendered.convert("RGB")
                assert pixels.getpixel((60, 60)) == (220, 30, 40)
                assert pixels.getpixel((200, 330)) == (31, 41, 51)
            assert ["fixture", "loaded"] in font_states
            if policy == "filehost":
                assert outside_headers == [None]
            if shared_application is not None:
                with pytest.raises(ResourceAccessDenied):
                    await shared_application.resources.read_bytes(picture)
                await compact._close_application()
                with pytest.raises(ProviderLifecycleError):
                    async with compact.get_new_page():
                        pytest.fail("A borrowed browser must not bypass compact shutdown")
                async with shared_application.extensions.playwright.page() as page:
                    await page.set_content("<title>shared still open</title>")
                    assert await page.title() == "shared still open"
        finally:
            await compact._close_application()
            if shared_application is not None:
                await shared_application.aclose()
            set_default_application(original_application)
            if hosted_store is not None:
                await hosted_store.aclose()


@pytest.mark.asyncio
async def test_shutdown_rejects_requests_while_cleanup_is_waiting(htmlrender_08, tmp_path, monkeypatch):
    import asyncio

    from nonebot_plugin_htmlrender.rendering.errors import ProviderLifecycleError

    from nonebot_plugin_skland import compact

    template = tmp_path / "closing.html.jinja2"
    template.write_text("ready", encoding="utf-8")
    await compact.template_to_html(str(tmp_path), template.name)
    application = compact._get_application()
    close_application = application.aclose
    closing = asyncio.Event()
    release = asyncio.Event()

    async def slow_close():
        closing.set()
        await release.wait()
        await close_application()

    monkeypatch.setattr(application, "aclose", slow_close)
    cleanup = asyncio.ensure_future(compact._close_application())
    try:
        await closing.wait()
        with pytest.raises(ProviderLifecycleError):
            async with compact.get_new_page():
                pytest.fail("Shutdown admission must close before asynchronous cleanup finishes")
    finally:
        release.set()
        await cleanup
