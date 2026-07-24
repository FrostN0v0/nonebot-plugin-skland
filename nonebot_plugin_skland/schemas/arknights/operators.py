import re
from enum import Enum
from typing import Any, cast
from difflib import get_close_matches
from dataclasses import field, dataclass

from pydantic import Field, BaseModel
from nonebot.compat import model_validator

from .models.base import Equip
from .models.status import Status
from .models.assist_chars import Equipment
from .models.chars import Skill, Character
from .game_data import OperatorCatalog, OperatorCatalogEntry
from ...filters import (
    ark_roster_lh_url,
    ark_rarity_icon_url,
    ark_roster_light_url,
    ark_skin_portrait_url,
    ark_uniequip_icon_url,
    ark_profession_icon_url,
)


class OperatorOwnership(str, Enum):
    OWNED = "owned"
    UNOWNED = "unowned"
    ALL = "all"

    @property
    def label(self) -> str:
        return {
            type(self).OWNED: "已拥有",
            type(self).UNOWNED: "未拥有",
            type(self).ALL: "全部干员",
        }[self]

    @property
    def roster_title(self) -> str:
        return {
            type(self).OWNED: "Operator Box",
            type(self).UNOWNED: "Missing Operators",
            type(self).ALL: "Operator Book",
        }[self]


class OperatorSort(str, Enum):
    RELEASE = "release"
    ACQUIRED = "acquired"
    TRAINING = "training"

    @property
    def label(self) -> str:
        return {
            type(self).RELEASE: "实装顺序",
            type(self).ACQUIRED: "获取顺序",
            type(self).TRAINING: "练度顺序",
        }[self]


PROFESSION_ALIASES = {
    "先锋": "先锋",
    "近卫": "近卫",
    "重装": "重装",
    "狙击": "狙击",
    "术师": "术师",
    "术士": "术师",
    "医疗": "医疗",
    "辅助": "辅助",
    "特种": "特种",
    "pioneer": "先锋",
    "vanguard": "先锋",
    "warrior": "近卫",
    "guard": "近卫",
    "tank": "重装",
    "defender": "重装",
    "sniper": "狙击",
    "caster": "术师",
    "medic": "医疗",
    "support": "辅助",
    "supporter": "辅助",
    "special": "特种",
    "specialist": "特种",
}

POSITION_ALIASES = {
    "近战": "近战位",
    "近战位": "近战位",
    "melee": "近战位",
    "远程": "远程位",
    "远程位": "远程位",
    "ranged": "远程位",
}

GENDER_ALIASES = {
    "男": "男",
    "男性": "男",
    "male": "男",
    "女": "女",
    "女性": "女",
    "女士": "女",
    "female": "女",
    "其他": "其他",
    "未知": "其他",
    "other": "其他",
}

OWNERSHIP_ALIASES = {
    "owned": OperatorOwnership.OWNED,
    "持有": OperatorOwnership.OWNED,
    "已拥有": OperatorOwnership.OWNED,
    "unowned": OperatorOwnership.UNOWNED,
    "未拥有": OperatorOwnership.UNOWNED,
    "缺失": OperatorOwnership.UNOWNED,
    "未持有": OperatorOwnership.UNOWNED,
    "缺干员": OperatorOwnership.UNOWNED,
    "all": OperatorOwnership.ALL,
    "全部": OperatorOwnership.ALL,
    "图鉴": OperatorOwnership.ALL,
}

SORT_ALIASES = {
    "release": OperatorSort.RELEASE,
    "实装": OperatorSort.RELEASE,
    "实装顺序": OperatorSort.RELEASE,
    "acquired": OperatorSort.ACQUIRED,
    "gain": OperatorSort.ACQUIRED,
    "获取": OperatorSort.ACQUIRED,
    "最近": OperatorSort.ACQUIRED,
    "最近获得": OperatorSort.ACQUIRED,
    "获取顺序": OperatorSort.ACQUIRED,
    "training": OperatorSort.TRAINING,
    "练度": OperatorSort.TRAINING,
    "练度排序": OperatorSort.TRAINING,
}


def _split_values(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return ()
    return tuple(item for item in re.split(r"[,，\s]+", str(raw).strip()) if item)


def _parse_levels(raw: str | None, label: str) -> frozenset[int]:
    if raw is None or not str(raw).strip():
        return frozenset()
    text = str(raw).strip().lower()
    if text in {"all", "*", "a", "全部"}:
        return frozenset()

    levels: set[int] = set()
    for item in _split_values(text.replace("~", "-")):
        part = item.removesuffix("星").removesuffix("潜")
        if "-" in part:
            left, _, right = part.partition("-")
            try:
                lower, upper = int(left), int(right)
            except ValueError as error:
                raise ValueError(f"无效{label}：{raw}") from error
            if lower > upper:
                lower, upper = upper, lower
            if lower < 1 or upper > 6:
                raise ValueError(f"{label}范围必须在 1-6：{part}")
            levels.update(range(lower, upper + 1))
            continue
        try:
            level = int(part)
        except ValueError as error:
            raise ValueError(f"无效{label}：{raw}") from error
        if level not in range(1, 7):
            raise ValueError(f"{label}范围必须在 1-6：{level}")
        levels.add(level)
    return frozenset(levels)


def _parse_ownership(raw: str | None) -> OperatorOwnership:
    if raw is None or not str(raw).strip():
        return OperatorOwnership.OWNED
    value = OWNERSHIP_ALIASES.get(str(raw).strip().casefold())
    if value is None:
        raise ValueError(f"未知持有状态：{raw}；可选 owned / unowned / all")
    return value


def _parse_sort(raw: str | None) -> OperatorSort:
    if raw is None or not str(raw).strip():
        return OperatorSort.RELEASE
    value = SORT_ALIASES.get(str(raw).strip().casefold())
    if value is None:
        raise ValueError(f"未知排序方式：{raw}；可选 release / acquired / training")
    return value


def _resolve_values(
    raw: str | None,
    aliases: dict[str, str],
    label: str,
) -> frozenset[str]:
    if not raw:
        return frozenset()
    normalized_aliases = {key.casefold(): value for key, value in aliases.items()}
    values: set[str] = set()
    for item in _split_values(raw):
        value = normalized_aliases.get(item.casefold())
        if value is not None:
            values.add(value)
            continue
        suggestions = get_close_matches(item.casefold(), normalized_aliases, n=3, cutoff=0.4)
        suffix = f"；可能是：{'、'.join(normalized_aliases[key] for key in suggestions)}" if suggestions else ""
        raise ValueError(f"未知{label}：{item}{suffix}")
    return frozenset(values)


@dataclass(slots=True)
class _OperatorQueryPatch:
    ownership: OperatorOwnership | None = None
    sort: OperatorSort | None = None
    stars: set[int] = field(default_factory=set)
    professions: set[str] = field(default_factory=set)
    branches: set[str] = field(default_factory=set)
    positions: set[str] = field(default_factory=set)
    genders: set[str] = field(default_factory=set)
    factions: set[str] = field(default_factory=set)
    races: set[str] = field(default_factory=set)
    potentials: set[int] = field(default_factory=set)
    all_stars: bool = False
    all_potentials: bool = False
    name: str = ""


def _catalog_filter_aliases(
    catalog: OperatorCatalog,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    branch_aliases = {branch: branch for branch in catalog.branches}
    branch_aliases.update(catalog.branch_ids)
    faction_aliases = {faction: faction for faction in catalog.factions}
    faction_aliases.update({power_id: power_id for entry in catalog.entries for power_id in entry.power_ids})
    race_aliases = {race: race for race in catalog.races}
    race_aliases.update({"不明": "未知", "不公开": "未公开"})
    return branch_aliases, faction_aliases, race_aliases


def _is_all_value(raw: str | None) -> bool:
    return bool(raw) and str(raw).strip().casefold() in {"all", "*", "a", "全部"}


def _parse_query_tokens(catalog: OperatorCatalog, tokens: tuple[str, ...]) -> _OperatorQueryPatch:
    patch = _OperatorQueryPatch()
    branch_aliases, faction_aliases, race_aliases = _catalog_filter_aliases(catalog)
    profession_aliases = {key.casefold(): value for key, value in PROFESSION_ALIASES.items()}
    position_aliases = {key.casefold(): value for key, value in POSITION_ALIASES.items()}
    gender_aliases = {key.casefold(): value for key, value in GENDER_ALIASES.items()}
    normalized_branches = {key.casefold(): value for key, value in branch_aliases.items()}
    normalized_factions = {key.casefold(): value for key, value in faction_aliases.items()}
    normalized_races = {key.casefold(): value for key, value in race_aliases.items()}
    known_filters = {
        **profession_aliases,
        **position_aliases,
        **gender_aliases,
        **normalized_branches,
        **normalized_factions,
        **normalized_races,
    }

    for raw_token in tokens:
        for token in _split_values(raw_token):
            normalized = token.casefold()
            name_prefix, separator, name_value = token.replace("：", ":").partition(":")
            if separator and name_prefix.casefold() in {"名字", "名称", "name"}:
                name_value = name_value.strip()
                if not name_value:
                    raise ValueError("名称筛选不能为空")
                if patch.name and patch.name.casefold() != name_value.casefold():
                    raise ValueError("一次只能使用一个名称筛选")
                patch.name = name_value
                continue

            if ownership := OWNERSHIP_ALIASES.get(normalized):
                if patch.ownership is not None and patch.ownership is not ownership:
                    raise ValueError(f"持有状态不能同时为“{patch.ownership.label}”和“{ownership.label}”")
                patch.ownership = ownership
                continue
            if sort := SORT_ALIASES.get(normalized):
                if patch.sort is not None and patch.sort is not sort:
                    raise ValueError(f"排序方式不能同时为“{patch.sort.label}”和“{sort.label}”")
                patch.sort = sort
                continue
            if normalized == "满潜":
                patch.potentials.add(6)
                continue
            if potential_match := re.fullmatch(r"(?:潜能|潜)(.+)|(.+)潜", normalized):
                potential_text = potential_match.group(1) or potential_match.group(2)
                if _is_all_value(potential_text):
                    patch.all_potentials = True
                    patch.potentials.clear()
                elif not patch.all_potentials:
                    patch.potentials.update(_parse_levels(potential_text, "潜能"))
                continue
            if rarity_match := re.fullmatch(r"(.+?)(?:星级|星|★)", normalized):
                rarity_text = rarity_match.group(1)
                if _is_all_value(rarity_text):
                    patch.all_stars = True
                    patch.stars.clear()
                elif not patch.all_stars:
                    patch.stars.update(_parse_levels(rarity_text, "星级"))
                continue
            if value := profession_aliases.get(normalized):
                patch.professions.add(value)
                continue
            if value := position_aliases.get(normalized):
                patch.positions.add(value)
                continue
            if value := gender_aliases.get(normalized):
                patch.genders.add(value)
                continue
            if value := normalized_branches.get(normalized):
                patch.branches.add(value)
                continue
            if value := normalized_factions.get(normalized):
                patch.factions.add(value)
                continue
            if value := normalized_races.get(normalized):
                patch.races.add(value)
                continue

            if any(
                normalized in value.casefold()
                for entry in catalog.entries
                for value in (entry.name, entry.appellation, entry.char_id)
            ):
                if patch.name and patch.name.casefold() != normalized:
                    raise ValueError("一次只能使用一个名称筛选")
                patch.name = token
                continue

            suggestions = get_close_matches(normalized, known_filters, n=3, cutoff=0.5)
            suffix = f"；可能是：{'、'.join(known_filters[key] for key in suggestions)}" if suggestions else ""
            raise ValueError(f"无法识别筛选词：{token}{suffix}；筛选词之间请使用空格")
    return patch


def _validate_query_constraints(
    ownership: OperatorOwnership,
    sort: OperatorSort,
    potentials: set[int] | frozenset[int],
) -> None:
    if ownership is OperatorOwnership.UNOWNED and potentials:
        raise ValueError("未拥有干员没有潜能数据，不能同时筛选未拥有和潜能")
    if ownership is OperatorOwnership.UNOWNED and sort is OperatorSort.ACQUIRED:
        raise ValueError("未拥有干员没有获取时间，不能按获取顺序排序")
    if ownership is OperatorOwnership.UNOWNED and sort is OperatorSort.TRAINING:
        raise ValueError("未拥有干员没有练度数据，不能按练度排序")


class OperatorRosterQuery(BaseModel):
    ownership: OperatorOwnership = OperatorOwnership.OWNED
    sort: OperatorSort = OperatorSort.RELEASE
    stars: frozenset[int] = Field(default_factory=frozenset)
    professions: frozenset[str] = Field(default_factory=frozenset)
    branches: frozenset[str] = Field(default_factory=frozenset)
    positions: frozenset[str] = Field(default_factory=frozenset)
    genders: frozenset[str] = Field(default_factory=frozenset)
    factions: frozenset[str] = Field(default_factory=frozenset)
    races: frozenset[str] = Field(default_factory=frozenset)
    potentials: frozenset[int] = Field(default_factory=frozenset)
    name: str = ""

    @model_validator(mode="after")
    @classmethod
    def validate_ownership_constraints(cls, values: Any) -> Any:
        ownership = cast(
            OperatorOwnership,
            values.get("ownership") if isinstance(values, dict) else values.ownership,
        )
        sort = cast(OperatorSort, values.get("sort") if isinstance(values, dict) else values.sort)
        potentials = cast(
            set[int] | frozenset[int],
            values.get("potentials", frozenset()) if isinstance(values, dict) else values.potentials,
        )
        _validate_query_constraints(ownership, sort, potentials)
        return values

    @classmethod
    def from_raw(
        cls,
        catalog: OperatorCatalog,
        *,
        ownership: str | None = None,
        rarities: str | None = None,
        professions: str | None = None,
        branches: str | None = None,
        positions: str | None = None,
        genders: str | None = None,
        factions: str | None = None,
        races: str | None = None,
        potentials: str | None = None,
        name: str | None = None,
        sort: str | None = None,
    ) -> "OperatorRosterQuery":
        return cls.from_input(
            catalog,
            ownership=ownership,
            rarities=rarities,
            professions=professions,
            branches=branches,
            positions=positions,
            genders=genders,
            factions=factions,
            races=races,
            potentials=potentials,
            name=name,
            sort=sort,
        )

    @classmethod
    def from_input(
        cls,
        catalog: OperatorCatalog,
        *,
        filters: tuple[str, ...] = (),
        ownership: str | None = None,
        rarities: str | None = None,
        professions: str | None = None,
        branches: str | None = None,
        positions: str | None = None,
        genders: str | None = None,
        factions: str | None = None,
        races: str | None = None,
        potentials: str | None = None,
        name: str | None = None,
        sort: str | None = None,
    ) -> "OperatorRosterQuery":
        patch = _parse_query_tokens(catalog, filters)
        branch_aliases, faction_aliases, race_aliases = _catalog_filter_aliases(catalog)

        explicit_ownership = _parse_ownership(ownership) if ownership and str(ownership).strip() else None
        if explicit_ownership is not None and patch.ownership is not None and explicit_ownership is not patch.ownership:
            raise ValueError(f"持有状态不能同时为“{explicit_ownership.label}”和“{patch.ownership.label}”")
        parsed_ownership = explicit_ownership or patch.ownership or OperatorOwnership.OWNED

        explicit_sort = _parse_sort(sort) if sort and str(sort).strip() else None
        if explicit_sort is not None and patch.sort is not None and explicit_sort is not patch.sort:
            raise ValueError(f"排序方式不能同时为“{explicit_sort.label}”和“{patch.sort.label}”")
        parsed_sort = explicit_sort or patch.sort or OperatorSort.RELEASE

        parsed_stars = set(_parse_levels(rarities, "星级"))
        if _is_all_value(rarities) or patch.all_stars:
            parsed_stars.clear()
        else:
            parsed_stars.update(patch.stars)

        parsed_potentials = set(_parse_levels(potentials, "潜能"))
        if _is_all_value(potentials) or patch.all_potentials:
            parsed_potentials.clear()
        else:
            parsed_potentials.update(patch.potentials)

        parsed_name = (name or "").strip()
        if parsed_name and patch.name and parsed_name.casefold() != patch.name.casefold():
            raise ValueError("一次只能使用一个名称筛选")
        parsed_name = parsed_name or patch.name

        _validate_query_constraints(parsed_ownership, parsed_sort, parsed_potentials)
        return cls(
            ownership=parsed_ownership,
            sort=parsed_sort,
            stars=frozenset(parsed_stars),
            professions=frozenset(set(_resolve_values(professions, PROFESSION_ALIASES, "职业")) | patch.professions),
            branches=frozenset(set(_resolve_values(branches, branch_aliases, "职业分支")) | patch.branches),
            positions=frozenset(set(_resolve_values(positions, POSITION_ALIASES, "部署位置")) | patch.positions),
            genders=frozenset(set(_resolve_values(genders, GENDER_ALIASES, "性别")) | patch.genders),
            factions=frozenset(set(_resolve_values(factions, faction_aliases, "势力")) | patch.factions),
            races=frozenset(set(_resolve_values(races, race_aliases, "种族")) | patch.races),
            potentials=frozenset(parsed_potentials),
            name=parsed_name,
        )

    def matches(self, entry: OperatorCatalogEntry, character: Character | None) -> bool:
        if self.ownership is OperatorOwnership.OWNED and character is None:
            return False
        if self.ownership is OperatorOwnership.UNOWNED and character is not None:
            return False
        if self.stars and entry.star not in self.stars:
            return False
        if self.professions and entry.profession not in self.professions:
            return False
        if self.branches and entry.sub_profession_name not in self.branches:
            return False
        if self.positions and entry.position not in self.positions:
            return False
        if self.genders and entry.gender not in self.genders:
            return False
        if self.factions and not self.factions.intersection(entry.powers | entry.power_ids):
            return False
        if self.races and not self.races.intersection(entry.races):
            return False
        if self.potentials and (character is None or character.potential_level not in self.potentials):
            return False
        if self.name:
            query = self.name.casefold()
            if all(query not in value.casefold() for value in (entry.name, entry.appellation, entry.char_id)):
                return False
        return True

    @property
    def tags(self) -> list[str]:
        if not self.stars:
            star_tag = "全部星级"
        elif len(self.stars) == 1:
            star_tag = f"{next(iter(self.stars))}★"
        else:
            star_tag = f"{'/'.join(str(star) for star in sorted(self.stars, reverse=True))}★"
        tags = [self.ownership.label, self.sort.label, star_tag]
        for values in (
            self.professions,
            self.branches,
            self.positions,
            self.genders,
            self.factions,
            self.races,
        ):
            if values:
                tags.append("/".join(sorted(values)))
        if self.potentials:
            levels = "/".join(str(level) for level in sorted(self.potentials, reverse=True))
            tags.append(f"潜能 {levels}")
        if self.name:
            tags.append(f"名称：{self.name}")
        return tags

    @property
    def summary(self) -> str:
        return " · ".join(self.tags)


class OperatorModule(BaseModel):
    type_icon: str
    equipment: Equip | None = None
    selected: bool = False

    @property
    def icon(self) -> str:
        return ark_uniequip_icon_url(self.type_icon)

    @property
    def level(self) -> int:
        return self.equipment.level if self.equipment is not None else 0

    @property
    def locked(self) -> bool:
        return self.equipment is None or self.equipment.locked


class OperatorCard(BaseModel):
    entry: OperatorCatalogEntry
    character: Character | None = None
    skills: list[Skill] = Field(default_factory=list)
    modules: list[OperatorModule] = Field(default_factory=list)

    @classmethod
    def from_entry(
        cls,
        entry: OperatorCatalogEntry,
        character: Character | None,
        equipment_map: dict[str, Equipment] | None = None,
    ) -> "OperatorCard":
        equipment_map = equipment_map or {}
        owned_skills = {skill.id: skill for skill in character.skills if skill.id} if character else {}
        skill_ids = entry.skill_ids or tuple(owned_skills)
        skills = [owned_skills.get(skill_id) or Skill(id=skill_id, specializeLevel=0) for skill_id in skill_ids]
        modules = cls._build_modules(entry, character, equipment_map)
        return cls(entry=entry, character=character, skills=skills, modules=modules)

    @staticmethod
    def _build_modules(
        entry: OperatorCatalogEntry,
        character: Character | None,
        equipment_map: dict[str, Equipment],
    ) -> list[OperatorModule]:
        owned_by_id = {equipment.id: equipment for equipment in character.equip} if character else {}

        def resolve_type_icon(module_id: str, fallback: str) -> str:
            metadata = equipment_map.get(module_id)
            return metadata.typeIcon if metadata and metadata.typeIcon else fallback or "original"

        modules: list[OperatorModule] = []
        if entry.modules:
            for catalog_module in entry.modules:
                type_icon = resolve_type_icon(catalog_module.id, catalog_module.type_icon)
                if type_icon.casefold() == "original":
                    continue
                equipment = owned_by_id.get(catalog_module.id)
                modules.append(
                    OperatorModule(
                        type_icon=type_icon,
                        equipment=equipment,
                        selected=bool(
                            equipment
                            and not equipment.locked
                            and character
                            and character.defaultEquipId == equipment.id
                        ),
                    )
                )
            return modules

        if character is None:
            return modules
        for equipment in character.equip:
            type_icon = resolve_type_icon(equipment.id, "original")
            if type_icon.casefold() == "original":
                continue
            modules.append(
                OperatorModule(
                    type_icon=type_icon,
                    equipment=equipment,
                    selected=not equipment.locked and character.defaultEquipId == equipment.id,
                )
            )
        return modules

    @property
    def char_id(self) -> str:
        return self.entry.char_id

    @property
    def name(self) -> str:
        return self.entry.name

    @property
    def profession(self) -> str:
        return self.entry.profession

    @property
    def rarity(self) -> int:
        return self.entry.rarity

    @property
    def sort_id(self) -> int:
        return self.entry.sort_id

    @property
    def owned(self) -> bool:
        return self.character is not None

    @property
    def skin_id(self) -> str:
        return self.character.effective_skin_id if self.character else self.entry.default_skin_id

    @property
    def portrait(self) -> str:
        return self.character.portrait if self.character else ark_skin_portrait_url(self.entry.default_skin_id)

    @property
    def class_icon(self) -> str:
        return ark_profession_icon_url(self.entry.profession)

    @property
    def rarity_icon(self) -> str:
        return ark_rarity_icon_url(self.entry.rarity)

    @property
    def light(self) -> str:
        return ark_roster_light_url(self.entry.rarity)

    @property
    def lh(self) -> str:
        return ark_roster_lh_url(self.entry.rarity)

    @property
    def potential(self) -> str:
        return self.character.potential if self.character else ""

    @property
    def elite(self) -> str:
        return self.character.elite if self.character else ""

    @property
    def level_text(self) -> str:
        return self.character.level_text if self.character else ""

    @property
    def main_skill_level(self) -> int:
        return self.character.mainSkillLvl if self.character else 0

    @property
    def training_sort_key(self) -> tuple[int, ...]:
        if self.character is None:
            return ()
        module_levels = [module.level for module in self.modules if not module.locked]
        return (
            self.character.evolvePhase,
            self.character.level,
            self.character.mastery_total,
            self.character.mastery_three_count,
            max(module_levels, default=0),
            sum(module_levels),
            self.character.mainSkillLvl,
            self.character.favorPercent,
        )


class OperatorRoster(BaseModel):
    status: Status
    query: OperatorRosterQuery
    cards: list[OperatorCard] = Field(default_factory=list)

    @classmethod
    def build(
        cls,
        status: Status,
        catalog: OperatorCatalog,
        characters: list[Character],
        query: OperatorRosterQuery,
        equipment_map: dict[str, Equipment] | None = None,
    ) -> "OperatorRoster":
        owned_by_id = {character.charId: character for character in characters}
        entries = list(catalog.entries)
        entries.extend(
            OperatorCatalogEntry.fallback(char_id) for char_id in owned_by_id if char_id not in catalog.by_id
        )
        cards = [
            OperatorCard.from_entry(entry, character, equipment_map)
            for entry in entries
            if query.matches(entry, character := owned_by_id.get(entry.char_id))
        ]
        return cls(status=status, query=query, cards=cls._sort_cards(cards, query.sort))

    @staticmethod
    def _sort_cards(cards: list[OperatorCard], sort: OperatorSort) -> list[OperatorCard]:
        def release_key(card: OperatorCard) -> tuple[int, str]:
            return -card.sort_id, card.char_id

        if sort is OperatorSort.RELEASE:
            return sorted(cards, key=release_key)

        owned_cards = sorted((card for card in cards if card.character is not None), key=release_key)
        unowned_cards = sorted((card for card in cards if card.character is None), key=release_key)
        if sort is OperatorSort.ACQUIRED:
            owned_cards.sort(
                key=lambda card: (
                    bool(card.character and card.character.gainTime > 0),
                    card.character.gainTime if card.character else 0,
                ),
                reverse=True,
            )
        else:
            owned_cards.sort(
                key=lambda card: card.training_sort_key,
                reverse=True,
            )
        return [*owned_cards, *unowned_cards]

    @property
    def title(self) -> str:
        return self.query.ownership.roster_title

    @property
    def tags(self) -> list[str]:
        return self.query.tags

    @property
    def summary(self) -> str:
        return self.query.summary

    def with_cards(self, cards: list[OperatorCard]) -> "OperatorRoster":
        return type(self)(status=self.status, query=self.query, cards=cards)
