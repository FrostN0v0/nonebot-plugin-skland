"""游戏数据加载与管理"""

import os
import json
from typing import TYPE_CHECKING, Any

import httpx
from nonebot import logger
from nonebot.compat import model_dump

from .exception import RequestException
from .schemas.arknights.game_data import OperatorCatalog, OperatorMetadataSnapshot
from .config import DATA_DIR, DATA_ROUTES, GACHA_DATA_PATH, OPERATOR_METADATA_PATH, config

if TYPE_CHECKING:
    from .schemas import CharTable, GachaTable, GachaDetails
    from .schemas.endfield.gacha.base import EfGachaContentPool


def _json_default(value: Any) -> list[Any]:
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


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
        self.origin_version: str | None = None
        self.gacha_table: list[GachaTable] = []
        self.gacha_details: list[GachaDetails] = []
        self.character_table: list[CharTable] = []
        self.operator_catalog = OperatorCatalog()

    async def get_gacha_details(self):
        from .schemas import GachaDetails

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get("https://weedy.prts.wiki/gacha_table.json")
                response.raise_for_status()
                data = response.json()["gachaPoolClient"]
                self.gacha_details = [GachaDetails(**item) for item in data]
        except httpx.HTTPError as e:
            raise RequestException(f"获取卡池详情失败: {type(e).__name__}: {e}")

    async def get_version(self):
        from .download import GameResourceDownloader

        self.origin_version = await GameResourceDownloader.check_update(DATA_DIR)

    async def download_game_data(self):
        from .download import GameResourceDownloader

        for route in DATA_ROUTES:
            logger.info(f"正在下载: {route}")
            await GameResourceDownloader.download_all(
                owner="yuanyan3060",
                repo="ArknightsGameResource",
                route=route,
                save_dir=DATA_DIR,
                branch="main",
                update=True,
            )

    def _update_version_file(self) -> None:
        """更新本地版本文件"""
        if self.origin_version:
            self.version_file.write_text(self.origin_version, encoding="utf-8")
            self.version = self.origin_version

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
        except (OSError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"加载干员筛选元数据失败，将尝试重新获取: {e}")
            return None

    @staticmethod
    def _write_operator_metadata(snapshot: OperatorMetadataSnapshot) -> None:
        OPERATOR_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = OPERATOR_METADATA_PATH.with_suffix(".tmp")
        try:
            temporary_path.write_text(
                json.dumps(
                    model_dump(snapshot),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    default=_json_default,
                ),
                encoding="utf-8",
            )
            os.replace(temporary_path, OPERATOR_METADATA_PATH)
        finally:
            temporary_path.unlink(missing_ok=True)

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
        except ValueError as e:
            raise RequestException(f"校验 PRTS 干员筛选元数据失败: {e}")
        self._write_operator_metadata(snapshot)
        logger.info(f"✅ 干员筛选元数据更新完成，共 {len(snapshot.operators)} 条")
        return snapshot

    def load_operator_catalog(self) -> OperatorCatalog:
        try:
            tables = self._load_operator_tables()
            self.operator_catalog = self._build_operator_catalog(tables, self._load_operator_metadata())
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
            raise RequestException(f"加载干员目录失败，请尝试同步游戏数据: {e}")
        return self.operator_catalog

    async def load(self, force: bool = False, refresh_metadata: bool = False) -> bool:
        """加载卡池和干员目录数据，返回是否更新了本地数据。"""
        from .schemas import CharTable, GachaTable

        await self.get_version()
        if not self.version_file.exists() and self.origin_version:
            self._update_version_file()

        downloaded = False
        if force:
            logger.info("正在重新下载卡池数据...")
            await self.download_game_data()
            self._update_version_file()
            downloaded = True
        elif all(GACHA_DATA_PATH.joinpath(route.rsplit("/", maxsplit=1)[-1]).exists() for route in DATA_ROUTES):
            if self.version != self.origin_version and self.origin_version:
                logger.info("检测到卡池数据版本更新，正在重新下载卡池数据...")
                await self.download_game_data()
                self._update_version_file()
                downloaded = True
        else:
            await self.download_game_data()
            self._update_version_file()
            downloaded = True

        self.character_table = []
        self.gacha_table = []
        self.gacha_details = []

        try:
            tables = self._load_operator_tables()
            metadata_snapshot = self._load_operator_metadata()
            metadata_updated = False
            if force or refresh_metadata or downloaded or metadata_snapshot is None:
                try:
                    metadata_snapshot = await self._refresh_operator_metadata(tables)
                    metadata_updated = True
                except RequestException as e:
                    fallback = "旧缓存" if metadata_snapshot is not None else "官方档案数据"
                    logger.warning(f"干员筛选元数据更新失败，继续使用{fallback}: {e}")

            char_json = tables["character_table.json"]
            for char_id, data in char_json.items():
                char_table = CharTable(**data)
                char_table.char_id = char_id
                self.character_table.append(char_table)

            gacha_json = json.loads(GACHA_DATA_PATH.joinpath("gacha_table.json").read_text(encoding="utf-8"))
            self.gacha_table = [GachaTable(**item) for item in gacha_json.get("gachaPoolClient", [])]
            self.operator_catalog = self._build_operator_catalog(tables, metadata_snapshot)
            await self.get_gacha_details()
        except (OSError, ValueError, json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            logger.error(f"加载卡池数据失败: {type(e).__name__}: {e}")
            raise RequestException(f"加载卡池数据失败，请尝试删除数据目录后重新启动: {e}")

        return downloaded or metadata_updated


class EfGachaPoolTableData:
    """终末地卡池数据管理

    从 GitHub 仓库 FrostN0v0/EndfieldGachaPoolTable 拉取 GachaPoolTable.json，
    解析为 dict[str, EfGachaContentPool]，提供按 pool_id 查询卡池 UP 信息的能力。
    不做版本校验，每次启动或执行 sync 命令时直接覆盖下载。
    """

    RAW_URL = "https://raw.githubusercontent.com/FrostN0v0/EndfieldGachaPoolTable/master/GachaPoolTable.json"

    def __init__(self) -> None:
        self._file_path = DATA_DIR / "endfield" / "GachaPoolTable.json"
        self.pool_table: dict[str, EfGachaContentPool] = {}

    async def download(self) -> None:
        """从 GitHub 下载 GachaPoolTable.json（支持代理）"""
        url = f"{config.github_proxy_url}{self.RAW_URL}" if config.github_proxy_url else self.RAW_URL
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()
                self._file_path.parent.mkdir(parents=True, exist_ok=True)
                self._file_path.write_bytes(response.content)
                logger.info("✅ 终末地卡池数据下载完成")
        except httpx.HTTPError as e:
            raise RequestException(f"下载终末地卡池数据失败: {type(e).__name__}: {e}")

    async def load(self) -> None:
        """下载并加载终末地卡池数据

        下载失败时，若本地存在旧文件则使用旧缓存并发出警告，否则抛出异常。
        """
        try:
            await self.download()
        except RequestException as e:
            if self._file_path.exists():
                logger.warning(f"终末地卡池数据下载失败，使用本地缓存: {e}")
            else:
                raise

        self._parse()

    def _parse(self) -> None:
        """解析本地 GachaPoolTable.json"""
        from .schemas.endfield.gacha.base import EfGachaContentPool

        try:
            raw: dict = json.loads(self._file_path.read_text(encoding="utf-8"))
            self.pool_table = {pool_id: EfGachaContentPool(**data) for pool_id, data in raw.items()}
            logger.info(f"✅ 终末地卡池数据加载完成，共 {len(self.pool_table)} 个卡池")
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            logger.error(f"加载终末地卡池数据失败: {type(e).__name__}: {e}")
            raise RequestException(f"加载终末地卡池数据失败: {e}")

    def get_pool(self, pool_id: str) -> "EfGachaContentPool | None":
        """按 pool_id 查询卡池信息"""
        return self.pool_table.get(pool_id)


gacha_table_data = GachaTableData()
ef_gacha_pool_data = EfGachaPoolTableData()
