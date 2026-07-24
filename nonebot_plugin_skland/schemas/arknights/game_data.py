import re
from time import time
from typing import Any

from pydantic import Field, BaseModel
from nonebot.compat import model_validator

PROFESSION_NAMES = {
    "PIONEER": "先锋",
    "WARRIOR": "近卫",
    "TANK": "重装",
    "SNIPER": "狙击",
    "CASTER": "术师",
    "MEDIC": "医疗",
    "SUPPORT": "辅助",
    "SPECIAL": "特种",
}

POSITION_NAMES = {
    "MELEE": "近战位",
    "RANGED": "远程位",
}

PROFILE_FIELD_PATTERN = re.compile(r"【(?P<field>性别|种族)】(?P<value>[^\r\n]+)")


def normalize_operator_gender(value: str | None) -> str:
    text = (value or "").strip()
    if text in {"男", "男性", "male"}:
        return "男"
    if text in {"女", "女性", "女士", "female"}:
        return "女"
    return "其他" if text else ""


def normalize_operator_races(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    normalized: set[str] = set()
    for item in re.split(r"[/／、]", value):
        race = item.strip()
        if not race:
            continue
        if "不公开" in race:
            race = "未公开"
        elif race == "不明" or race.startswith("未知"):
            race = "未知"
        normalized.add(race)
    return frozenset(normalized)


class PerChar(BaseModel):
    rarityRank: int
    charIdList: list[str]


class UpCharInfo(BaseModel):
    perCharList: list[PerChar]


class AvailCharInfo(BaseModel):
    perAvailList: list[PerChar]


class GachaDetailInfo(BaseModel):
    upCharInfo: UpCharInfo | None = None
    availCharInfo: AvailCharInfo | None = None
    """UP角色信息"""


class GachaDetail(BaseModel):
    detailInfo: GachaDetailInfo
    """卡池详情"""


class GachaDetails(BaseModel):
    """抽卡详情"""

    gachaPoolDetail: GachaDetail
    gachaPoolId: str


class CharTable(BaseModel):
    """角色信息表"""

    char_id: str = ""
    """角色ID"""
    name: str
    """角色名称"""


class OperatorMetadata(BaseModel):
    char_id: str
    branch_name: str = ""
    gender: str = ""
    races: frozenset[str] = Field(default_factory=frozenset)

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        normalized = dict(values)
        normalized["gender"] = normalize_operator_gender(normalized.get("gender"))
        races = normalized.get("races")
        if isinstance(races, str):
            normalized["races"] = normalize_operator_races(races)
        elif races:
            normalized["races"] = frozenset(race for value in races for race in normalize_operator_races(str(value)))
        return normalized


class OperatorMetadataSnapshot(BaseModel):
    schema_version: int = 1
    source: str = "prts"
    fetched_at: int = Field(default_factory=lambda: int(time()))
    operators: tuple[OperatorMetadata, ...] = ()

    @model_validator(mode="after")
    @classmethod
    def ensure_unique_char_ids(cls, values: Any) -> Any:
        operators = values.get("operators", ()) if isinstance(values, dict) else values.operators
        char_ids = [operator.char_id for operator in operators]
        if not all(char_ids):
            raise ValueError("operator metadata contains an empty char_id")
        if len(char_ids) != len(set(char_ids)):
            raise ValueError("operator metadata contains duplicate char_id values")
        return values

    @property
    def by_id(self) -> dict[str, OperatorMetadata]:
        return {operator.char_id: operator for operator in self.operators}

    @classmethod
    def from_prts_rows(cls, rows: list[dict[str, Any]]) -> "OperatorMetadataSnapshot":
        operators: list[OperatorMetadata] = []
        for row in rows:
            data = row.get("title", row)
            operators.append(
                OperatorMetadata(
                    char_id=str(data.get("char_id") or "").strip(),
                    branch_name=str(data.get("branch") or "").strip(),
                    gender=normalize_operator_gender(str(data.get("gender") or "")),
                    races=normalize_operator_races(str(data.get("race") or "")),
                )
            )
        return cls(operators=tuple(operators))


class OperatorCatalogModule(BaseModel):
    id: str
    type_icon: str


class OperatorCatalogEntry(BaseModel):
    char_id: str
    name: str
    appellation: str
    profession: str
    rarity: int
    sort_id: int
    sub_profession_id: str = ""
    sub_profession_name: str = ""
    position: str = ""
    power_ids: frozenset[str] = Field(default_factory=frozenset)
    powers: frozenset[str] = Field(default_factory=frozenset)
    gender: str = ""
    races: frozenset[str] = Field(default_factory=frozenset)
    tags: frozenset[str] = Field(default_factory=frozenset)
    skill_ids: tuple[str, ...] = ()
    modules: tuple[OperatorCatalogModule, ...] = ()

    @property
    def star(self) -> int:
        return self.rarity + 1

    @property
    def default_skin_id(self) -> str:
        return f"{self.char_id}#1"

    @classmethod
    def fallback(cls, char_id: str) -> "OperatorCatalogEntry":
        return cls(
            char_id=char_id,
            name=char_id,
            appellation="",
            profession="",
            rarity=5,
            sort_id=-1,
        )


class OperatorCatalog(BaseModel):
    entries: tuple[OperatorCatalogEntry, ...] = ()

    @property
    def by_id(self) -> dict[str, OperatorCatalogEntry]:
        return {entry.char_id: entry for entry in self.entries}

    @property
    def branches(self) -> frozenset[str]:
        return frozenset(entry.sub_profession_name for entry in self.entries if entry.sub_profession_name)

    @property
    def branch_ids(self) -> dict[str, str]:
        return {
            entry.sub_profession_id.casefold(): entry.sub_profession_name
            for entry in self.entries
            if entry.sub_profession_id and entry.sub_profession_name
        }

    @property
    def factions(self) -> frozenset[str]:
        return frozenset(power for entry in self.entries for power in entry.powers)

    @property
    def races(self) -> frozenset[str]:
        return frozenset(race for entry in self.entries for race in entry.races)

    @classmethod
    def from_game_tables(
        cls,
        character_table: dict[str, dict[str, Any]],
        char_patch_table: dict[str, Any],
        uniequip_table: dict[str, Any],
        handbook_info_table: dict[str, Any],
        handbook_team_table: dict[str, dict[str, Any]],
        metadata_snapshot: OperatorMetadataSnapshot | None = None,
    ) -> "OperatorCatalog":
        characters = {
            char_id: data
            for char_id, data in character_table.items()
            if char_id.startswith("char_") and not data.get("isNotObtainable", False)
        }
        patch_characters = char_patch_table.get("patchChars") or {}
        characters.update(patch_characters)

        handbook_dict = handbook_info_table.get("handbookDict") or {}
        release_order = {char_id: index for index, char_id in enumerate(handbook_dict)}
        base_sort_index: dict[tuple[str, str], int] = {}
        for char_id, data in character_table.items():
            release_index = release_order.get(char_id, -1)
            if release_index < 0:
                continue
            for key in ("potentialItemId", "displayNumber"):
                value = data.get(key)
                if value:
                    base_sort_index[(key, value)] = release_index

        patch_base_by_id: dict[str, str] = {}
        for base_id, info in (char_patch_table.get("infos") or {}).items():
            for patch_id in info.get("tmplIds") or ():
                patch_base_by_id[patch_id] = base_id

        handbook_profiles = {char_id: _parse_handbook_profile(data) for char_id, data in handbook_dict.items()}
        metadata_by_id = metadata_snapshot.by_id if metadata_snapshot else {}
        branch_names: dict[str, str] = {}
        for char_id, data in characters.items():
            metadata = metadata_by_id.get(char_id)
            branch_id = str(data.get("subProfessionId") or "")
            if metadata and metadata.branch_name and branch_id:
                branch_names.setdefault(branch_id, metadata.branch_name)

        char_equip = uniequip_table.get("charEquip") or {}
        equip_dict = uniequip_table.get("equipDict") or {}
        entries: list[OperatorCatalogEntry] = []
        for char_id, data in characters.items():
            profession_key = data.get("profession")
            profession = PROFESSION_NAMES.get(profession_key) if isinstance(profession_key, str) else None
            rarity = data.get("rarity")
            if profession is None or not isinstance(rarity, int) or rarity not in range(6):
                continue
            position_key = data.get("position")
            position = POSITION_NAMES.get(position_key, position_key) if isinstance(position_key, str) else ""

            sort_index = release_order.get(char_id, -1)
            if char_id in patch_characters:
                for key in ("potentialItemId", "displayNumber"):
                    value = data.get(key)
                    if value and (key, value) in base_sort_index:
                        sort_index = base_sort_index[(key, value)]
                        break

            modules = tuple(
                OperatorCatalogModule(
                    id=module_id,
                    type_icon=module.get("typeIcon") or "original",
                )
                for module_id in char_equip.get(char_id, [])
                if (module := equip_dict.get(module_id)) is not None
            )

            main_power = data.get("mainPower") or data
            power_ids = frozenset(
                str(power_id) for key in ("nationId", "groupId", "teamId") if (power_id := main_power.get(key))
            )
            powers = frozenset(
                (handbook_team_table.get(power_id) or {}).get("powerName") or power_id for power_id in power_ids
            )

            base_id = patch_base_by_id.get(char_id, char_id)
            fallback_metadata = handbook_profiles.get(base_id)
            metadata = metadata_by_id.get(char_id)
            branch_id = str(data.get("subProfessionId") or "")
            entries.append(
                OperatorCatalogEntry(
                    char_id=char_id,
                    name=data.get("name") or char_id,
                    appellation=data.get("appellation") or "",
                    profession=profession,
                    rarity=rarity,
                    sort_id=sort_index,
                    sub_profession_id=branch_id,
                    sub_profession_name=(
                        (metadata.branch_name if metadata else "") or branch_names.get(branch_id) or branch_id
                    ),
                    position=position,
                    power_ids=power_ids,
                    powers=powers,
                    gender=(metadata.gender if metadata else "")
                    or (fallback_metadata.gender if fallback_metadata else ""),
                    races=(metadata.races if metadata else frozenset())
                    or (fallback_metadata.races if fallback_metadata else frozenset()),
                    tags=frozenset(data.get("tagList") or ()),
                    skill_ids=tuple(skill["skillId"] for skill in data.get("skills") or () if skill.get("skillId")),
                    modules=modules,
                )
            )
        entries.sort(key=lambda entry: (-entry.sort_id, entry.char_id))
        return cls(entries=tuple(entries))


def _parse_handbook_profile(data: dict[str, Any]) -> OperatorMetadata:
    fields: dict[str, str] = {}
    for section in data.get("storyTextAudio") or ():
        for story in section.get("stories") or ():
            text = story.get("storyText") or ""
            for match in PROFILE_FIELD_PATTERN.finditer(text):
                fields.setdefault(match.group("field"), match.group("value").strip())
        if "性别" in fields and "种族" in fields:
            break
    return OperatorMetadata(
        char_id=str(data.get("charID") or ""),
        gender=normalize_operator_gender(fields.get("性别")),
        races=normalize_operator_races(fields.get("种族")),
    )
