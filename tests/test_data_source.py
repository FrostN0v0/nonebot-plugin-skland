"""Offline data-update regressions using real loaders and an HTTP transport."""

import json
from pathlib import Path
from copy import deepcopy

import httpx
import pytest

HTTP_CLIENT = httpx.AsyncClient
COMMIT = "a" * 40


def _tables(label):
    return {
        "gacha_table.json": {
            "gachaPoolClient": [
                {"gachaPoolId": "pool", "gachaPoolName": label, "openTime": 1, "endTime": 2, "gachaRuleType": 0}
            ]
        },
        "character_table.json": {
            "char_test": {
                "name": label,
                "profession": "WARRIOR",
                "rarity": 5,
                "position": "MELEE",
                "subProfessionId": "fighter",
                "nationId": "test",
            }
        },
        "char_patch_table.json": {"patchChars": {}, "infos": {}, "label": label},
        "uniequip_table.json": {"charEquip": {}, "equipDict": {}, "label": label},
        "handbook_info_table.json": {"handbookDict": {}, "label": label},
        "handbook_team_table.json": {"test": {"powerName": label}},
    }


def _endfield(label):
    return {
        "pool": {
            "pool_name": label,
            "up6_name": label,
            "all": [{"id": "char_test", "name": label, "rarity": 6}],
        }
    }


class DataServer:
    def __init__(self):
        self.version = "old\n"
        self.tables = _tables("old")
        self.endfield = _endfield("old")
        self.details = {"gachaPoolClient": [{"gachaPoolId": "pool", "gachaPoolDetail": {"detailInfo": {}}}]}
        self.requests = []
        self.fail_file = None
        self.fail_ref = False
        self.prts_offline = False
        self.invalid_details = False

    def respond(self, request):
        self.requests.append(request.url)
        if request.url.host == "api.github.com":
            assert "/git/ref/heads/" in request.url.path
            if self.fail_ref:
                return httpx.Response(403)
            return httpx.Response(200, json={"object": {"type": "commit", "sha": COMMIT}})
        if request.url.host == "raw.githubusercontent.com":
            assert f"/{COMMIT}/" in request.url.path
            filename = request.url.path.rsplit("/", 1)[-1]
            if filename == self.fail_file:
                return httpx.Response(404)
            if filename == "version":
                return httpx.Response(200, text=self.version)
            if filename == "GachaPoolTable.json":
                if isinstance(self.endfield, str):
                    return httpx.Response(200, text=self.endfield)
                return httpx.Response(200, json=self.endfield)
            return httpx.Response(200, json=self.tables[filename])
        if self.prts_offline:
            return httpx.Response(403)
        if request.url.host == "weedy.prts.wiki":
            return httpx.Response(200, json={"gachaPoolClient": [{}]} if self.invalid_details else self.details)
        assert request.url.host == "prts.wiki"
        return httpx.Response(
            200,
            json={
                "cargoquery": [
                    {"title": {"char_id": "char_test", "branch": "New Branch", "gender": "女", "race": "Race"}}
                ]
            },
        )


@pytest.fixture
def data_update(app, tmp_path, monkeypatch):
    from nonebot_plugin_skland.config import config
    import nonebot_plugin_skland.download as download
    import nonebot_plugin_skland.data_source as source

    server = DataServer()
    transport = httpx.MockTransport(server.respond)
    monkeypatch.setattr(source, "DATA_DIR", tmp_path)
    monkeypatch.setattr(source, "GACHA_DATA_PATH", tmp_path / "gamedata" / "excel")
    monkeypatch.setattr(source, "OPERATOR_METADATA_PATH", tmp_path / "operator_metadata.json")
    monkeypatch.setattr(config, "github_proxy_url", "")
    monkeypatch.setattr(download, "AsyncClient", lambda **kwargs: HTTP_CLIENT(transport=transport, **kwargs))
    monkeypatch.setattr(source.httpx, "AsyncClient", lambda **kwargs: HTTP_CLIENT(transport=transport, **kwargs))
    return source, server


def _seed_ark(source, server):
    from nonebot_plugin_skland.schemas import OperatorMetadata, OperatorMetadataSnapshot

    source.GACHA_DATA_PATH.mkdir(parents=True)
    for filename, raw in server.tables.items():
        (source.GACHA_DATA_PATH / filename).write_text(json.dumps(raw), encoding="utf-8")
    (source.DATA_DIR / "version").write_text("old\n", encoding="utf-8")
    source.GachaTableData._write_operator_metadata(
        OperatorMetadataSnapshot(operators=(OperatorMetadata(char_id="char_test", branch_name="Old Branch"),))
    )
    (source.DATA_DIR / "gacha_details.json").write_bytes(source._json_bytes(server.details))


def _disk_snapshot(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.mark.asyncio
async def test_equal_version_with_newline_keeps_tables_and_loads_consumers(data_update):
    source, server = data_update
    _seed_ark(source, server)
    before = _disk_snapshot(source.DATA_DIR)
    loader = source.GachaTableData()

    assert await loader.load() is False

    assert loader.version == "old"
    assert loader.character_table[0].name == "old"
    assert loader.gacha_table[0].gachaPoolName == "old"
    assert loader.operator_catalog.by_id["char_test"].sub_profession_name == "Old Branch"
    assert loader.gacha_details[0].gachaPoolId == "pool"
    assert _disk_snapshot(source.DATA_DIR) == before
    assert not any("/gamedata/" in url.path for url in server.requests)


@pytest.mark.asyncio
async def test_successful_update_publishes_coherent_tables_without_tree_enumeration(data_update):
    source, server = data_update
    server.version = "new\n"
    server.tables = _tables("new")
    loader = source.GachaTableData()

    assert await loader.load() is True

    assert loader.version_file.read_text(encoding="utf-8") == "new"
    assert loader.character_table[0].name == "new"
    assert loader.gacha_table[0].gachaPoolName == "new"
    assert loader.operator_catalog.by_id["char_test"].powers == frozenset({"new"})
    for filename, raw in server.tables.items():
        assert json.loads((source.GACHA_DATA_PATH / filename).read_text(encoding="utf-8")) == raw
    raw_tables = [url for url in server.requests if "/gamedata/" in url.path]
    assert {url.path.rsplit("/", 1)[-1] for url in raw_tables} == set(server.tables)
    assert not any("/git/trees/" in url.path for url in server.requests)


@pytest.mark.parametrize("failure", ["http", "json", "catalog"])
@pytest.mark.asyncio
async def test_invalid_sixth_table_preserves_disk_version_and_warm_state(data_update, failure):
    source, server = data_update
    from nonebot_plugin_skland.exception import RequestException

    _seed_ark(source, server)
    loader = source.GachaTableData()
    await loader.load()
    old_characters = loader.character_table
    old_pools = loader.gacha_table
    old_catalog = loader.operator_catalog
    before = _disk_snapshot(source.DATA_DIR)
    server.version = "new"
    server.tables = _tables("new")
    if failure == "http":
        server.fail_file = "handbook_team_table.json"
    elif failure == "json":
        server.tables["handbook_team_table.json"] = ["invalid"]
    else:
        server.tables["handbook_team_table.json"] = {"test": "invalid"}

    with pytest.raises(RequestException):
        await loader.load()

    assert _disk_snapshot(source.DATA_DIR) == before
    assert loader.version == "old"
    assert loader.character_table is old_characters
    assert loader.gacha_table is old_pools
    assert loader.operator_catalog is old_catalog


@pytest.mark.parametrize("failure", ["ref", "version", "table"])
@pytest.mark.asyncio
async def test_cold_start_uses_valid_cache_but_reports_remote_failure(data_update, failure):
    source, server = data_update
    from nonebot_plugin_skland.exception import RequestException

    _seed_ark(source, server)
    before = _disk_snapshot(source.DATA_DIR)
    server.fail_ref = failure == "ref"
    if failure == "version":
        server.fail_file = "version"
    elif failure == "table":
        server.version = "new"
        server.fail_file = "handbook_team_table.json"
    loader = source.GachaTableData()

    with pytest.raises(RequestException):
        await loader.load()

    assert loader.character_table[0].name == "old"
    assert loader.gacha_table[0].gachaPoolName == "old"
    assert loader.operator_catalog.by_id["char_test"].sub_profession_name == "Old Branch"
    assert loader.gacha_details[0].gachaPoolId == "pool"
    assert _disk_snapshot(source.DATA_DIR) == before


@pytest.mark.asyncio
async def test_failed_first_download_never_publishes_version_or_partial_data(data_update):
    source, server = data_update
    from nonebot_plugin_skland.exception import RequestException

    server.fail_file = "handbook_team_table.json"
    loader = source.GachaTableData()
    with pytest.raises(RequestException):
        await loader.load()

    assert _disk_snapshot(source.DATA_DIR) == {}
    assert loader.version is None
    assert loader.character_table == []
    assert loader.gacha_table == []
    assert loader.operator_catalog.entries == ()


@pytest.mark.parametrize("target", ["handbook_team_table.json", "version"])
@pytest.mark.asyncio
async def test_publication_failure_rolls_back_all_files(data_update, monkeypatch, target):
    source, server = data_update
    from nonebot_plugin_skland.exception import RequestException

    _seed_ark(source, server)
    loader = source.GachaTableData()
    await loader.load()
    before = _disk_snapshot(source.DATA_DIR)
    server.version = "new"
    server.tables = _tables("new")
    replace = source.os.replace
    failed = False

    def fail_once(src, destination):
        nonlocal failed
        if Path(destination).name == target and not failed:
            failed = True
            raise OSError("publication denied")
        return replace(src, destination)

    monkeypatch.setattr(source.os, "replace", fail_once)
    with pytest.raises(RequestException):
        await loader.load()

    assert _disk_snapshot(source.DATA_DIR) == before
    assert loader.version == "old"
    assert loader.character_table[0].name == "old"
    assert loader.operator_catalog.by_id["char_test"].name == "old"


@pytest.mark.asyncio
async def test_optional_prts_failure_keeps_metadata_and_persisted_details_on_cold_start(data_update):
    source, server = data_update
    first_loader = source.GachaTableData()
    await first_loader.load()
    before = _disk_snapshot(source.DATA_DIR)
    server.prts_offline = True
    cold_loader = source.GachaTableData()

    assert await cold_loader.load(refresh_metadata=True) is False

    assert cold_loader.operator_catalog.by_id["char_test"].sub_profession_name == "New Branch"
    assert cold_loader.gacha_details[0].gachaPoolId == "pool"
    assert _disk_snapshot(source.DATA_DIR) == before


@pytest.mark.asyncio
async def test_invalid_prts_details_preserve_prior_memory_and_cache(data_update):
    source, server = data_update
    from nonebot_plugin_skland.exception import RequestException

    loader = source.GachaTableData()
    await loader.get_gacha_details()
    before = _disk_snapshot(source.DATA_DIR)
    details = loader.gacha_details
    server.invalid_details = True
    with pytest.raises(RequestException):
        await loader.get_gacha_details()

    assert loader.gacha_details is details
    assert _disk_snapshot(source.DATA_DIR) == before


@pytest.mark.parametrize(
    "response", ["<html>Bad gateway</html>", [], {"pool": {}}, {"pool": {"pool_name": "new", "all": [{}]}}]
)
@pytest.mark.asyncio
async def test_invalid_endfield_response_keeps_old_cache_and_loads_cold_fallback(data_update, response):
    source, server = data_update
    from nonebot_plugin_skland.exception import RequestException

    first_loader = source.EfGachaPoolTableData()
    await first_loader.load()
    before = first_loader._file_path.read_bytes()
    server.endfield = response
    loader = source.EfGachaPoolTableData()
    with pytest.raises(RequestException):
        await loader.load()

    assert loader._file_path.read_bytes() == before
    assert loader.get_pool("pool").pool_name == "old"
    assert loader.get_pool("pool").up_six_char_ids == ["char_test"]


@pytest.mark.asyncio
async def test_endfield_success_and_force_avoid_rewriting_equivalent_data(data_update, monkeypatch):
    source, server = data_update
    loader = source.EfGachaPoolTableData()
    assert await loader.load() is True
    server.endfield = _endfield("new")
    assert await loader.load(force=True) is True
    assert loader.get_pool("pool").up_six_display_name == "new"
    assert json.loads(loader._file_path.read_text(encoding="utf-8")) == server.endfield
    before = loader._file_path.read_bytes()
    server.endfield = deepcopy(server.endfield)
    server.endfield["pool"]["up5_name"] = ""

    def reject_rewrite(*args):
        raise AssertionError("Equivalent validated data must not replace the cache")

    monkeypatch.setattr(source.os, "replace", reject_rewrite)
    assert await loader.load(force=True) is False
    assert loader._file_path.read_bytes() == before


@pytest.mark.asyncio
async def test_endfield_disk_failure_preserves_warm_pool(data_update, monkeypatch):
    source, server = data_update
    from nonebot_plugin_skland.exception import RequestException

    loader = source.EfGachaPoolTableData()
    await loader.load()
    old_pool = loader.get_pool("pool")
    before = loader._file_path.read_bytes()
    server.endfield = _endfield("new")

    def reject_publication(*args):
        raise OSError("read-only cache")

    monkeypatch.setattr(source.os, "replace", reject_publication)
    with pytest.raises(RequestException):
        await loader.load()

    assert loader.get_pool("pool") is old_pool
    assert loader._file_path.read_bytes() == before


@pytest.mark.asyncio
async def test_equal_version_repairs_invalid_required_cache(data_update):
    source, server = data_update
    _seed_ark(source, server)
    (source.GACHA_DATA_PATH / "handbook_team_table.json").write_text("[]", encoding="utf-8")
    loader = source.GachaTableData()

    assert await loader.load() is True

    assert loader.operator_catalog.by_id["char_test"].powers == frozenset({"old"})
    assert (
        json.loads((source.GACHA_DATA_PATH / "handbook_team_table.json").read_text(encoding="utf-8"))
        == server.tables["handbook_team_table.json"]
    )
    assert loader.version == "old"


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.asyncio
async def test_endfield_http_failure_reports_failure_without_losing_cache(data_update, cached):
    source, server = data_update
    from nonebot_plugin_skland.exception import RequestException

    if cached:
        await source.EfGachaPoolTableData().load()
    before = _disk_snapshot(source.DATA_DIR)
    server.fail_file = "GachaPoolTable.json"
    loader = source.EfGachaPoolTableData()

    with pytest.raises(RequestException):
        await loader.load()

    assert _disk_snapshot(source.DATA_DIR) == before
    if cached:
        assert loader.get_pool("pool").up_six_display_name == "old"
    else:
        assert loader.pool_table == {}


@pytest.mark.asyncio
async def test_first_publication_keeps_version_absent_until_all_tables_exist(data_update, monkeypatch):
    source, server = data_update
    replace = source.os.replace
    version = source.DATA_DIR / "version"

    def observe_publication(src, destination):
        destination = Path(destination)
        if destination.parent == source.GACHA_DATA_PATH:
            assert not version.exists()
        elif destination == version:
            for filename, raw in server.tables.items():
                assert json.loads((source.GACHA_DATA_PATH / filename).read_text(encoding="utf-8")) == raw
        return replace(src, destination)

    monkeypatch.setattr(source.os, "replace", observe_publication)
    loader = source.GachaTableData()
    assert await loader.load() is True
    assert version.read_text(encoding="utf-8") == "old"
    assert loader.gacha_table[0].gachaPoolName == "old"


@pytest.mark.asyncio
async def test_first_download_with_empty_cache_is_not_a_warning(data_update):
    source, _ = data_update
    source.GACHA_DATA_PATH.mkdir(parents=True)
    warnings = []
    sink = source.logger.add(lambda message: warnings.append(message.record["message"]), level="WARNING")
    try:
        await source.GachaTableData().load()
        await source.EfGachaPoolTableData().load()
    finally:
        source.logger.remove(sink)
    assert warnings == []


@pytest.mark.asyncio
async def test_corrupt_existing_caches_still_report_validation_warnings(data_update):
    source, server = data_update
    _seed_ark(source, server)
    endfield = source.EfGachaPoolTableData()
    await endfield.load()
    (source.GACHA_DATA_PATH / "character_table.json").write_text("not JSON", encoding="utf-8")
    endfield._file_path.write_text("not JSON", encoding="utf-8")
    warnings = []
    sink = source.logger.add(lambda message: warnings.append(message.record["message"]), level="WARNING")
    try:
        await source.GachaTableData().load()
        await source.EfGachaPoolTableData().load()
    finally:
        source.logger.remove(sink)
    assert len(warnings) == 2
    assert all("JSONDecodeError" in warning for warning in warnings)
