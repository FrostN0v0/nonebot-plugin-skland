"""游戏数据加载与管理"""

import os
import json
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any
from tempfile import NamedTemporaryFile

import httpx
from nonebot import logger
from nonebot.compat import model_dump

from .exception import RequestException
from .config import DATA_DIR, DATA_ROUTES, GACHA_DATA_PATH, OPERATOR_METADATA_PATH
from .schemas.arknights.game_data import OperatorCatalog, OperatorMetadataSnapshot

if TYPE_CHECKING:
    from .download import GitHubDataClient
    from .schemas import CharTable, GachaTable, GachaDetails
    from .schemas.endfield.gacha.base import EfGachaContentPool


def _json_default(value: Any) -> list[Any]:
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=_json_default).encode("utf-8")


def _publish_files(files: dict[Path, bytes]) -> bool:
    """Stage a small data batch, preserving originals until every replacement succeeds.

    The caller inserts its version marker last. This handles in-process failures;
    it is not a crash-atomic transaction across multiple filesystem paths.
    """
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path | None] = {}
    published: list[Path] = []
    temporary: list[Path] = []
    retained: set[Path] = set()
    try:
        for path, content in files.items():
            previous = path.read_bytes() if path.exists() else None
            if previous == content:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            for payload, destination in ((content, staged), (previous, backups)):
                if payload is None:
                    backups[path] = None
                    continue
                with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as file:
                    temporary_path = Path(file.name)
                    temporary.append(temporary_path)
                    file.write(payload)
                destination[path] = temporary_path
        for path, temporary_path in staged.items():
            os.replace(temporary_path, path)
            published.append(path)
    except OSError:
        for path in reversed(published):
            backup = backups[path]
            try:
                if backup is None:
                    path.unlink(missing_ok=True)
                else:
                    os.replace(backup, path)
            except OSError:
                if backup is not None:
                    retained.add(backup)
                logger.error(f"恢复游戏数据文件失败，保留备份: {path.name}")
        raise
    finally:
        for temporary_path in temporary:
            if temporary_path not in retained:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning(f"清理游戏数据临时文件失败: {temporary_path.name}")
    return bool(published)


class GachaTableData:
    """明日方舟卡池数据管理"""

    PRTS_API_URL = "https://prts.wiki/api.php"
    PRTS_PAGE_SIZE = 500
    OPERATOR_TABLE_FILES = (
        "character_table.json",
        "char_patch_table.json",
        "uniequip_table.json",
        "handbook_info_table.json",
        "handbook_team_table.json",
    )

    def __init__(self) -> None:
        self.version_file = DATA_DIR / "version"
        self.version: str | None = None
        if self.version_file.exists():
            try:
                self.version = self.version_file.read_text(encoding="utf-8").strip()
            except Exception as e:
                logger.warning(f"读取版本文件失败: {e}")
        self._details_path = DATA_DIR / "gacha_details.json"
        self.gacha_table: list[GachaTable] = []
        self.gacha_details: list[GachaDetails] = []
        self.character_table: list[CharTable] = []
        self.operator_catalog = OperatorCatalog()
        self._metadata_snapshot: OperatorMetadataSnapshot | None = None

    @staticmethod
    def _parse_gacha_details(raw: Any) -> list["GachaDetails"]:
        from .schemas import GachaDetails

        if not isinstance(raw, dict) or not isinstance(raw.get("gachaPoolClient"), list) or not raw["gachaPoolClient"]:
            raise ValueError("卡池详情为空或格式错误")
        return [GachaDetails(**item) for item in raw["gachaPoolClient"]]

    def _load_gacha_details(self) -> None:
        if self.gacha_details or not self._details_path.exists():
            return
        try:
            self.gacha_details = self._parse_gacha_details(json.loads(self._details_path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError) as e:
            logger.warning(f"加载卡池详情缓存失败: {type(e).__name__}")

    async def get_gacha_details(self) -> bool:
        """Refresh optional PRTS details without discarding a validated fallback."""
        self._load_gacha_details()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get("https://weedy.prts.wiki/gacha_table.json")
                response.raise_for_status()
                raw = response.json()
            details = self._parse_gacha_details(raw)
            changed = _publish_files({self._details_path: _json_bytes(raw)})
        except (httpx.HTTPError, OSError, ValueError, TypeError) as e:
            raise RequestException(f"获取卡池详情失败: {type(e).__name__}") from e
        self.gacha_details = details
        return changed

    def _load_operator_tables(self) -> dict[str, dict[str, Any]]:
        return {
            filename: json.loads(GACHA_DATA_PATH.joinpath(filename).read_text(encoding="utf-8"))
            for filename in self.OPERATOR_TABLE_FILES
        }

    @staticmethod
    def _build_operator_catalog(
        tables: dict[str, dict[str, Any]],
        metadata_snapshot: OperatorMetadataSnapshot | None,
    ) -> OperatorCatalog:
        return OperatorCatalog.from_game_tables(
            tables["character_table.json"],
            tables["char_patch_table.json"],
            tables["uniequip_table.json"],
            tables["handbook_info_table.json"],
            tables["handbook_team_table.json"],
            metadata_snapshot,
        )

    @staticmethod
    def _load_operator_metadata() -> OperatorMetadataSnapshot | None:
        if not OPERATOR_METADATA_PATH.exists():
            return None
        try:
            return OperatorMetadataSnapshot(**json.loads(OPERATOR_METADATA_PATH.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError) as e:
            logger.warning(f"加载干员筛选元数据失败，将尝试重新获取: {e}")
            return None

    @staticmethod
    def _write_operator_metadata(snapshot: OperatorMetadataSnapshot) -> bool:
        return _publish_files({OPERATOR_METADATA_PATH: _json_bytes(model_dump(snapshot))})

    async def _fetch_prts_operator_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        try:
            async with httpx.AsyncClient(
                timeout=30,
                headers={"User-Agent": "nonebot-plugin-skland operator metadata updater"},
            ) as client:
                while True:
                    response = await client.get(
                        self.PRTS_API_URL,
                        params={
                            "action": "cargoquery",
                            "format": "json",
                            "tables": "chara,chara_extra_info",
                            "fields": (
                                "chara.charId=char_id,chara.subProfession=branch,"
                                "chara_extra_info.sex=gender,chara_extra_info.race=race"
                            ),
                            "join_on": "chara._pageName=chara_extra_info._pageName",
                            "where": "chara.charIndex>0",
                            "limit": self.PRTS_PAGE_SIZE,
                            "offset": offset,
                        },
                    )
                    response.raise_for_status()
                    page = response.json().get("cargoquery") or []
                    rows.extend(page)
                    if len(page) < self.PRTS_PAGE_SIZE:
                        break
                    offset += self.PRTS_PAGE_SIZE
        except (httpx.HTTPError, ValueError, TypeError) as e:
            raise RequestException(f"获取 PRTS 干员筛选元数据失败: {type(e).__name__}: {e}")
        if not rows:
            raise RequestException("获取 PRTS 干员筛选元数据失败: 返回数据为空")
        return rows

    def _validate_operator_metadata(
        self,
        snapshot: OperatorMetadataSnapshot,
        tables: dict[str, dict[str, Any]],
    ) -> None:
        catalog = self._build_operator_catalog(tables, snapshot)
        official_ids = {entry.char_id for entry in catalog.entries}
        metadata_ids = set(snapshot.by_id)
        matched_count = len(official_ids.intersection(metadata_ids))
        minimum_count = max(1, int(len(official_ids) * 0.75))
        if matched_count < minimum_count:
            raise RequestException(f"PRTS 干员筛选元数据覆盖率过低: {matched_count}/{len(official_ids)}")

        branch_names: dict[str, str] = {}
        for entry in catalog.entries:
            metadata = snapshot.by_id.get(entry.char_id)
            if not metadata or not metadata.branch_name or not entry.sub_profession_id:
                continue
            previous = branch_names.setdefault(entry.sub_profession_id, metadata.branch_name)
            if previous != metadata.branch_name:
                raise RequestException(
                    f"PRTS 职业分支名称冲突: {entry.sub_profession_id} -> {previous}/{metadata.branch_name}"
                )

    async def _refresh_operator_metadata(
        self,
        tables: dict[str, dict[str, Any]],
    ) -> OperatorMetadataSnapshot:
        try:
            snapshot = OperatorMetadataSnapshot.from_prts_rows(await self._fetch_prts_operator_rows())
            self._validate_operator_metadata(snapshot, tables)
            self._write_operator_metadata(snapshot)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
            raise RequestException(f"校验或保存 PRTS 干员筛选元数据失败: {type(e).__name__}") from e
        logger.info(f"✅ 干员筛选元数据更新完成，共 {len(snapshot.operators)} 条")
        return snapshot

    def load_operator_catalog(self) -> OperatorCatalog:
        try:
            tables = self._load_operator_tables()
            metadata = self._load_operator_metadata() or self._metadata_snapshot
            catalog = self._build_operator_catalog(tables, metadata)
            if not catalog.entries:
                raise ValueError("干员目录为空")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
            raise RequestException(f"加载干员目录失败，请尝试同步游戏数据: {type(e).__name__}") from e
        self.operator_catalog = catalog
        self._metadata_snapshot = metadata
        return catalog

    def _parse_tables(
        self,
        tables: dict[str, dict[str, Any]],
        metadata: OperatorMetadataSnapshot | None,
    ) -> tuple[list["CharTable"], list["GachaTable"], OperatorCatalog]:
        from .schemas import CharTable, GachaTable

        for table in tables.values():
            if not isinstance(table, dict) or not table:
                raise ValueError("游戏数据表为空或格式错误")
        for filename, fields in (
            ("char_patch_table.json", ("patchChars", "infos")),
            ("uniequip_table.json", ("charEquip", "equipDict")),
            ("handbook_info_table.json", ("handbookDict",)),
        ):
            if any(not isinstance(tables[filename].get(field), dict) for field in fields):
                raise ValueError(f"游戏数据表结构错误: {filename}")
        if any(not isinstance(value, dict) for value in tables["handbook_team_table.json"].values()):
            raise ValueError("干员阵营数据格式错误")
        raw_pools = tables["gacha_table.json"].get("gachaPoolClient")
        if not isinstance(raw_pools, list) or not raw_pools:
            raise ValueError("卡池列表为空或格式错误")
        characters = []
        for char_id, data in tables["character_table.json"].items():
            character = CharTable(**data)
            character.char_id = char_id
            characters.append(character)
        pools = [GachaTable(**item) for item in raw_pools]
        catalog = self._build_operator_catalog(tables, metadata)
        if not catalog.entries:
            raise ValueError("干员目录为空")
        return characters, pools, catalog

    async def load(
        self,
        force: bool = False,
        refresh_metadata: bool = False,
        *,
        client: "GitHubDataClient | None" = None,
    ) -> bool:
        """Validate and publish data, restoring usable cache before reporting failures."""
        from .download import GitHubDataClient

        if client is None:
            async with GitHubDataClient() as owned_client:
                return await self.load(force, refresh_metadata, client=owned_client)

        metadata = self._load_operator_metadata() or self._metadata_snapshot
        self._load_gacha_details()
        cached_tables: dict[str, dict[str, Any]] = {}
        cached_state = None
        local_version = None
        cached_paths = (GACHA_DATA_PATH / route.rsplit("/", 1)[-1] for route in DATA_ROUTES)
        if self.version_file.exists() or any(path.exists() for path in cached_paths):
            try:
                tables = self._load_operator_tables()
                tables["gacha_table.json"] = json.loads(
                    (GACHA_DATA_PATH / "gacha_table.json").read_text(encoding="utf-8")
                )
                cached_state = self._parse_tables(tables, metadata)
                cached_tables = tables
                if self.version_file.exists():
                    local_version = self.version_file.read_text(encoding="utf-8").strip()
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
                logger.warning(f"本地游戏数据不完整，将尝试更新: {type(e).__name__}")

        try:
            commit = await client.resolve_commit("yuanyan3060", "ArknightsGameResource", "main")
            base = f"https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/{commit}/"
            version = (await client.get_text(f"{base}version")).strip()
            if not version:
                raise ValueError("游戏数据版本为空")
            changed = False
            if force or cached_state is None or local_version != version:
                if force:
                    logger.info("正在重新下载卡池数据...")
                elif cached_state is not None:
                    logger.info("检测到卡池数据版本更新，正在重新下载卡池数据...")
                # Wait for every request to settle before the borrowed client can close.
                results = await asyncio.gather(
                    *(client.get_json(f"{base}{route}") for route in DATA_ROUTES),
                    return_exceptions=True,
                )
                tables = {}
                for route, result in zip(DATA_ROUTES, results):
                    if isinstance(result, BaseException):
                        raise result
                    tables[route.rsplit("/", 1)[-1]] = result
                state = self._parse_tables(tables, metadata)
                files = {
                    GACHA_DATA_PATH / filename: _json_bytes(raw)
                    for filename, raw in tables.items()
                    if cached_state is None or cached_tables[filename] != raw
                }
                if local_version != version:
                    files[self.version_file] = version.encode("utf-8")
                changed = _publish_files(files)
            else:
                tables = cached_tables
                state = cached_state
        except (RequestException, httpx.HTTPError, OSError, ValueError, TypeError, KeyError, AttributeError) as e:
            if cached_state is not None and not self.character_table:
                self.character_table, self.gacha_table, self.operator_catalog = cached_state
                self.version = local_version
            reason = str(e) if isinstance(e, RequestException) else type(e).__name__
            raise RequestException(f"更新明日方舟游戏数据失败: {reason}") from e

        self.character_table, self.gacha_table, self.operator_catalog = state
        self.version = version
        self._metadata_snapshot = metadata
        if force or refresh_metadata or changed or metadata is None:
            try:
                previous_metadata = OPERATOR_METADATA_PATH.read_bytes() if OPERATOR_METADATA_PATH.exists() else None
                metadata = await self._refresh_operator_metadata(tables)
                self.operator_catalog = self._build_operator_catalog(tables, metadata)
                self._metadata_snapshot = metadata
                changed = changed or previous_metadata != _json_bytes(model_dump(metadata))
            except (RequestException, OSError) as e:
                fallback = "旧缓存" if metadata is not None else "官方档案数据"
                logger.warning(f"干员筛选元数据更新失败，继续使用{fallback}: {e}")
        try:
            details_changed = await self.get_gacha_details()
            changed = changed or details_changed
        except RequestException as e:
            logger.warning(f"卡池详情更新失败，继续使用可用缓存: {e}")
        return changed


class EfGachaPoolTableData:
    """终末地卡池数据管理，校验成功后才发布数据。"""

    def __init__(self) -> None:
        self._file_path = DATA_DIR / "endfield" / "GachaPoolTable.json"
        self.pool_table: dict[str, EfGachaContentPool] = {}

    @staticmethod
    def _parse(raw: Any) -> dict[str, "EfGachaContentPool"]:
        from .schemas.endfield.gacha.base import EfGachaContentPool

        if not isinstance(raw, dict) or not raw:
            raise ValueError("终末地卡池列表为空或格式错误")
        pools = {}
        for pool_id, data in raw.items():
            if not pool_id or not isinstance(data, dict) or not data.get("pool_name"):
                raise ValueError("终末地卡池数据格式错误")
            pools[pool_id] = EfGachaContentPool(**data)
        return pools

    async def load(self, *, force: bool = False, client: "GitHubDataClient | None" = None) -> bool:
        from .download import GitHubDataClient

        if client is None:
            async with GitHubDataClient() as owned_client:
                return await self.load(force=force, client=owned_client)

        cached = None
        if self._file_path.exists():
            try:
                cached = self._parse(json.loads(self._file_path.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError) as e:
                logger.warning(f"加载终末地卡池缓存失败: {type(e).__name__}")
        try:
            commit = await client.resolve_commit("FrostN0v0", "EndfieldGachaPoolTable", "master")
            raw = await client.get_json(
                f"https://raw.githubusercontent.com/FrostN0v0/EndfieldGachaPoolTable/{commit}/GachaPoolTable.json"
            )
            pools = self._parse(raw)
            # Endfield has no version marker: even force validates fresh data, but
            # equivalent validated contents never need rewriting.
            changed = False
            if cached != pools:
                changed = _publish_files({self._file_path: _json_bytes(raw)})
                logger.info("✅ 终末地卡池数据下载完成")
        except (RequestException, httpx.HTTPError, OSError, ValueError, TypeError) as e:
            if not self.pool_table and cached is not None:
                self.pool_table = cached
            reason = str(e) if isinstance(e, RequestException) else type(e).__name__
            raise RequestException(f"更新终末地卡池数据失败: {reason}") from e
        self.pool_table = pools
        return changed

    def get_pool(self, pool_id: str) -> "EfGachaContentPool | None":
        """按 pool_id 查询卡池信息"""
        return self.pool_table.get(pool_id)


gacha_table_data = GachaTableData()
ef_gacha_pool_data = EfGachaPoolTableData()
