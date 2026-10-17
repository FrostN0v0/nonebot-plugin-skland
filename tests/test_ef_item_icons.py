"""Official resource construction and localstore publication regressions."""

import json
from copy import deepcopy

import httpx
import pytest

HTTP_CLIENT = httpx.AsyncClient


class OfficialIconServer:
    def __init__(self):
        self.names = {
            "chr_0004_pelica": "佩丽卡",
            "chr_0036_jsspsi": "祀",
            "wpn_claym_0018": "玉中身",
            "wpn_lance_0004": "嵌合正义",
        }
        self.keys = {"chr_0004_pelica": "perlica", "chr_0036_jsspsi": "jsspsi"}
        self.icons = {
            "chr_0004_pelica": "https://web.hycdn.cn/avatars/perlica.png",
            "chr_0036_jsspsi": "https://web.hycdn.cn/avatars/si.png",
            "wpn_claym_0018": "https://bbs.hycdn.cn/weapons/jade.png",
            "wpn_lance_0004": "https://bbs.hycdn.cn/weapons/justice.png",
        }
        self.css_file = "icons-build1.css"
        self.fail = None
        self.html_override = None
        self.css_override = None
        self.catalog_override = None
        self.refresh_override = None
        self.device_payload = {"code": 1100, "detail": {"deviceId": "public-visitor-device"}}
        self.redirects = {}
        self.requests = []

    def operator_html(self):
        if self.html_override is not None:
            return self.html_override
        cards = []
        for item_id, key in self.keys.items():
            cards.append(
                '<div class="OperatorItem_operatorItem__newBuild">'
                f'<div class="OperatorItem_image__newBuild" data-key="{key}" '
                'style="background-image:url(https://web.hycdn.cn/wrong-portrait.png)"></div>'
                '<div class="OperatorItem_contentBlock__newBuild">'
                f'<span class="OperatorItem_nameText__newBuild"> {self.names[item_id]} </span>'
                '<i data-key="unrelated-profession"></i></div></div>'
            )
        return f'<link rel="stylesheet" href="https://web.hycdn.cn/official/{self.css_file}">' + "".join(cards)

    def stylesheet(self):
        if self.css_override is not None:
            return self.css_override
        return "".join(
            f'.switcher .__02-Operator_image__newBuild[data-key="{key}"]'
            f'{{background-image:url("{self.icons[item_id]}")}}'
            for item_id, key in self.keys.items()
        )

    def catalog(self):
        if self.catalog_override is not None:
            return self.catalog_override
        return {
            "catalog": [
                {
                    "id": "1",
                    "typeSub": [
                        {
                            "id": "2",
                            "items": [
                                {"name": f" {name} ", "brief": {"cover": self.icons[item_id]}}
                                for item_id, name in self.names.items()
                                if item_id.startswith("wpn_")
                            ],
                        }
                    ],
                }
            ]
        }

    def respond(self, request):
        self.requests.append(request.url)
        host, path = request.url.host, request.url.path
        if destination := self.redirects.get((host, path)):
            return httpx.Response(302, headers={"Location": destination})
        if host == "endfield.hypergryph.com" and path == "/operator":
            return httpx.Response(503) if self.fail == "operator" else httpx.Response(200, text=self.operator_html())
        if host == "web.hycdn.cn" and path.endswith(self.css_file):
            return httpx.Response(503) if self.fail == "stylesheet" else httpx.Response(200, text=self.stylesheet())
        if host == "fp-it.portal101.cn":
            if self.fail == "device":
                return httpx.Response(503)
            return httpx.Response(200, json=self.device_payload)
        if host == "zonai.skland.com":
            assert "cred" not in request.headers
            assert "authorization" not in request.headers
            if path == "/web/v1/auth/refresh":
                if self.fail == "refresh":
                    return httpx.Response(503)
                payload = self.refresh_override
                if payload is None:
                    payload = {"code": 0, "data": {"token": "public-visitor-token"}}
                return httpx.Response(200, json=payload)
            if path == "/web/v1/wiki/item/catalog":
                if self.fail == "catalog":
                    return httpx.Response(503)
                return httpx.Response(200, json={"code": 0, "data": self.catalog()})
        raise AssertionError(f"Unexpected resource request: {request.url}")


@pytest.fixture
def official_icons(app, tmp_path, monkeypatch):
    import nonebot_plugin_skland.data_source as source
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfGachaContentPool

    server = OfficialIconServer()
    transport = httpx.MockTransport(server.respond)
    monkeypatch.setattr(source, "DATA_DIR", tmp_path)
    monkeypatch.setattr(source.httpx, "AsyncClient", lambda **kwargs: HTTP_CLIENT(transport=transport, **kwargs))
    pools = [
        EfGachaContentPool(
            pool_name="当前卡池",
            all=[{"id": item_id, "name": name, "rarity": 6} for item_id, name in server.names.items()],
        )
    ]
    return source, server, pools


@pytest.mark.asyncio
async def test_official_pages_build_game_id_icons_in_localstore(official_icons):
    source, server, pools = official_icons
    loader = source.EfItemIconData()

    assert await loader.load(pools)
    assert loader.icons == server.icons
    assert json.loads(loader._file_path.read_text(encoding="utf-8")) == server.icons
    assert loader._file_path == source.DATA_DIR / "endfield" / "ItemIconTable.json"
    assert {url.host for url in server.requests} == {
        "endfield.hypergryph.com",
        "web.hycdn.cn",
        "fp-it.portal101.cn",
        "zonai.skland.com",
    }
    assert loader.get_icon("unknown") == ""


@pytest.mark.asyncio
async def test_historical_names_resolve_by_stable_item_identity(official_icons):
    source, server, pools = official_icons
    from nonebot_plugin_skland.schemas.endfield.gacha.base import EfGachaContentPool

    pools.append(
        EfGachaContentPool(pool_name="历史卡池", all=[{"id": "wpn_claym_0018", "name": "旧译名", "rarity": 6}])
    )
    loader = source.EfItemIconData()
    await loader.load(pools)
    assert loader.get_icon("wpn_claym_0018") == server.icons["wpn_claym_0018"]


@pytest.mark.asyncio
async def test_changed_assets_and_css_build_publish_without_rewriting_equal_force_result(official_icons, monkeypatch):
    source, server, pools = official_icons
    loader = source.EfItemIconData()
    await loader.load(pools)
    server.css_file = "icons-build2.css"
    server.icons["chr_0036_jsspsi"] = "https://web.hycdn.cn/avatars/si-new.png"
    server.icons["wpn_claym_0018"] = "https://bbs.hycdn.cn/weapons/jade-new.png"
    assert await loader.load(pools)
    assert loader.icons == server.icons
    before = loader._file_path.read_bytes()
    server.names = dict(reversed(list(server.names.items())))

    def reject_rewrite(*args):
        raise AssertionError("Equivalent official resources must not rewrite localstore")

    monkeypatch.setattr(source.os, "replace", reject_rewrite)
    assert await loader.load(pools, force=True) is False
    assert loader._file_path.read_bytes() == before


@pytest.mark.parametrize(
    "url",
    [
        None,
        "http://web.hycdn.cn/weapon.png",
        "https://web.hycdn.cn.evil.example/weapon.png",
        "https://web.hycdn.cn@evil.example/weapon.png",
        "https://third-party.example/weapon.png",
        "https://bbs.hycdn.cn/weapon.png#fragment",
        "https://bbs.hycdn.cn",
    ],
)
@pytest.mark.asyncio
async def test_invalid_official_cover_preserves_last_usable_table(official_icons, url):
    source, server, pools = official_icons
    from nonebot_plugin_skland.exception import RequestException

    loader = source.EfItemIconData()
    await loader.load(pools)
    old_icons, before = loader.icons, loader._file_path.read_bytes()
    server.icons["chr_0036_jsspsi"] = "https://web.hycdn.cn/avatars/si-new.png"
    server.icons["wpn_claym_0018"] = url
    with pytest.raises(RequestException):
        await loader.load(pools)
    assert loader.icons is old_icons
    assert loader._file_path.read_bytes() == before


@pytest.mark.parametrize(
    ("host", "path"),
    [
        ("endfield.hypergryph.com", "/operator"),
        ("web.hycdn.cn", "/official/icons-build1.css"),
        ("zonai.skland.com", "/web/v1/auth/refresh"),
        ("zonai.skland.com", "/web/v1/wiki/item/catalog"),
    ],
)
@pytest.mark.parametrize("destination", ["http://127.0.0.1/internal", "https://attacker.example/resource"])
@pytest.mark.asyncio
async def test_official_redirects_are_not_requested_and_preserve_cache(official_icons, host, path, destination):
    source, server, pools = official_icons
    from nonebot_plugin_skland.exception import RequestException

    loader = source.EfItemIconData()
    await loader.load(pools)
    old_icons, before = loader.icons, loader._file_path.read_bytes()
    server.redirects[host, path] = destination
    server.requests.clear()

    with pytest.raises(RequestException):
        await loader.load(pools)

    assert all(url.host != httpx.URL(destination).host for url in server.requests)
    assert loader.icons is old_icons
    assert loader._file_path.read_bytes() == before


@pytest.mark.parametrize("path", ["/web/v1/auth/refresh", "/web/v1/wiki/item/catalog"])
@pytest.mark.asyncio
async def test_wiki_rejects_redirects_even_with_following_client(official_icons, path):
    source, server, _ = official_icons
    server.redirects["zonai.skland.com", path] = "https://attacker.example/resource"

    async with HTTP_CLIENT(transport=httpx.MockTransport(server.respond), follow_redirects=True) as client:
        with pytest.raises(httpx.HTTPStatusError) as error:
            await source.get_endfield_weapon_catalog(client)

    assert error.value.response.status_code == 302
    assert all(url.host != "attacker.example" for url in server.requests)


@pytest.mark.parametrize(
    "payload",
    [[], {"code": 1100, "detail": ["invalid"]}, {"code": 1100, "detail": {"deviceId": 123}}],
    ids=["non-object-response", "non-object-detail", "non-string-device-id"],
)
@pytest.mark.asyncio
async def test_malformed_device_response_is_handled_and_preserves_cache(official_icons, payload):
    source, server, pools = official_icons
    from nonebot_plugin_skland.exception import RequestException

    loader = source.EfItemIconData()
    await loader.load(pools)
    old_icons, before = loader.icons, loader._file_path.read_bytes()
    server.device_payload = payload

    with pytest.raises(RequestException):
        await loader.load(pools)

    assert loader.icons is old_icons
    assert loader._file_path.read_bytes() == before


@pytest.mark.parametrize(
    "failure",
    ["operator", "stylesheet", "device", "refresh", "catalog", "markup", "avatar", "missing", "ambiguous", "visitor"],
)
@pytest.mark.asyncio
async def test_incomplete_official_update_never_publishes_partial_results(official_icons, failure):
    source, server, pools = official_icons
    from nonebot_plugin_skland.exception import RequestException

    loader = source.EfItemIconData()
    await loader.load(pools)
    old_icons, before = loader.icons, loader._file_path.read_bytes()
    server.icons["chr_0036_jsspsi"] = "https://web.hycdn.cn/avatars/si-new.png"
    if failure == "markup":
        server.html_override = "<html></html>"
    elif failure == "avatar":
        server.css_override = '.Other_image[data-key="jsspsi"]{background-image:url(https://web.hycdn.cn/wrong.png)}'
    elif failure == "missing":
        server.catalog_override = {"catalog": []}
    elif failure == "ambiguous":
        catalog = deepcopy(server.catalog())
        catalog["catalog"][0]["typeSub"][0]["items"].append(
            {"name": "玉中身", "brief": {"cover": "https://bbs.hycdn.cn/weapons/conflict.png"}}
        )
        server.catalog_override = catalog
    elif failure == "visitor":
        server.refresh_override = {"code": 10002, "data": None}
    else:
        server.fail = failure
    with pytest.raises(RequestException):
        await loader.load(pools)
    assert loader.icons is old_icons
    assert loader._file_path.read_bytes() == before


@pytest.mark.parametrize("invalid_cache", [False, True])
@pytest.mark.asyncio
async def test_first_run_offline_has_no_bundled_or_guessed_icons(official_icons, invalid_cache):
    source, server, pools = official_icons
    from nonebot_plugin_skland.exception import RequestException

    loader = source.EfItemIconData()
    invalid = b'{"wpn_test":"https://untrusted.example/icon.png"}'
    if invalid_cache:
        loader._file_path.parent.mkdir(parents=True)
        loader._file_path.write_bytes(invalid)
    server.fail = "operator"
    with pytest.raises(RequestException):
        await loader.load(pools)
    assert loader.icons == {}
    if invalid_cache:
        assert loader._file_path.read_bytes() == invalid
    else:
        assert not loader._file_path.exists()


@pytest.mark.asyncio
async def test_cold_start_restores_localstore_during_official_outage(official_icons):
    source, server, pools = official_icons
    from nonebot_plugin_skland.exception import RequestException

    first = source.EfItemIconData()
    await first.load(pools)
    before = first._file_path.read_bytes()
    server.fail = "catalog"
    cold = source.EfItemIconData()
    with pytest.raises(RequestException):
        await cold.load(pools)
    assert cold.icons == server.icons
    assert cold._file_path.read_bytes() == before


@pytest.mark.asyncio
async def test_failed_publication_preserves_last_successful_official_table(official_icons, monkeypatch):
    source, server, pools = official_icons
    from nonebot_plugin_skland.exception import RequestException

    loader = source.EfItemIconData()
    await loader.load(pools)
    old_icons, before = loader.icons, loader._file_path.read_bytes()
    server.icons["wpn_claym_0018"] = "https://bbs.hycdn.cn/weapons/jade-new.png"

    def reject_publication(*args):
        raise OSError("read-only localstore")

    monkeypatch.setattr(source.os, "replace", reject_publication)
    with pytest.raises(RequestException):
        await loader.load(pools)
    assert loader.icons is old_icons
    assert loader._file_path.read_bytes() == before


@pytest.mark.parametrize("cache", ["not JSON", '{"wpn_test":"https://untrusted.example/icon.png"}'])
@pytest.mark.asyncio
async def test_successful_official_update_repairs_invalid_localstore(official_icons, cache):
    source, server, pools = official_icons
    loader = source.EfItemIconData()
    loader._file_path.parent.mkdir(parents=True)
    loader._file_path.write_text(cache, encoding="utf-8")
    assert await loader.load(pools)
    assert json.loads(loader._file_path.read_text(encoding="utf-8")) == server.icons
