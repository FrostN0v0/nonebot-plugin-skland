import re
from difflib import get_close_matches

from pydantic import Field, BaseModel

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


def _split_values(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return ()
    return tuple(item for item in re.split(r"[,，\s]+", str(raw).strip()) if item)


def _parse_stars(raw: str | None) -> frozenset[int]:
    if raw is None or not str(raw).strip():
        return frozenset({6})
    text = str(raw).strip().lower()
    if text in {"all", "*", "a", "全部"}:
        return frozenset(range(1, 7))

    stars: set[int] = set()
    for item in _split_values(text.replace("~", "-")):
        part = item.removesuffix("星")
        if "-" in part:
            left, _, right = part.partition("-")
            try:
                lower, upper = int(left), int(right)
            except ValueError as error:
                raise ValueError(f"无效星级：{raw}") from error
            if lower > upper:
                lower, upper = upper, lower
            if lower < 1 or upper > 6:
                raise ValueError(f"星级范围必须在 1-6：{part}")
            stars.update(range(lower, upper + 1))
            continue
        try:
            star = int(part)
        except ValueError as error:
            raise ValueError(f"无效星级：{raw}") from error
        if star not in range(1, 7):
            raise ValueError(f"星级范围必须在 1-6：{star}")
        stars.add(star)
    return frozenset(stars or {6})


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


class OperatorFilter(BaseModel):
    stars: frozenset[int] = frozenset({6})
    professions: frozenset[str] = Field(default_factory=frozenset)
    branches: frozenset[str] = Field(default_factory=frozenset)
    positions: frozenset[str] = Field(default_factory=frozenset)
    genders: frozenset[str] = Field(default_factory=frozenset)
    factions: frozenset[str] = Field(default_factory=frozenset)
    races: frozenset[str] = Field(default_factory=frozenset)
    name: str = ""

    @classmethod
    def from_raw(
        cls,
        catalog: OperatorCatalog,
        *,
        rarities: str | None = None,
        professions: str | None = None,
        branches: str | None = None,
        positions: str | None = None,
        genders: str | None = None,
        factions: str | None = None,
        races: str | None = None,
        name: str | None = None,
    ) -> "OperatorFilter":
        branch_aliases = {branch: branch for branch in catalog.branches}
        branch_aliases.update(catalog.branch_ids)
        faction_aliases = {faction: faction for faction in catalog.factions}
        faction_aliases.update({power_id: power_id for entry in catalog.entries for power_id in entry.power_ids})
        race_aliases = {race: race for race in catalog.races}
        race_aliases.update({"不明": "未知", "不公开": "未公开"})
        return cls(
            stars=_parse_stars(rarities),
            professions=_resolve_values(professions, PROFESSION_ALIASES, "职业"),
            branches=_resolve_values(branches, branch_aliases, "职业分支"),
            positions=_resolve_values(positions, POSITION_ALIASES, "部署位置"),
            genders=_resolve_values(genders, GENDER_ALIASES, "性别"),
            factions=_resolve_values(factions, faction_aliases, "势力"),
            races=_resolve_values(races, race_aliases, "种族"),
            name=(name or "").strip(),
        )

    def matches(self, entry: OperatorCatalogEntry) -> bool:
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
        if self.name:
            query = self.name.casefold()
            if all(query not in value.casefold() for value in (entry.name, entry.appellation, entry.char_id)):
                return False
        return True

    @property
    def tags(self) -> list[str]:
        if self.stars == frozenset(range(1, 7)):
            star_tag = "全部星级"
        elif len(self.stars) == 1:
            star_tag = f"{next(iter(self.stars))}★"
        else:
            star_tag = f"{'/'.join(str(star) for star in sorted(self.stars, reverse=True))}★"
        tags = [star_tag]
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


class OperatorRoster(BaseModel):
    status: Status
    filter: OperatorFilter
    cards: list[OperatorCard] = Field(default_factory=list)
    book: bool = False

    @classmethod
    def build(
        cls,
        status: Status,
        catalog: OperatorCatalog,
        characters: list[Character],
        operator_filter: OperatorFilter,
        equipment_map: dict[str, Equipment] | None = None,
        *,
        book: bool = False,
    ) -> "OperatorRoster":
        owned_by_id = {character.charId: character for character in characters}
        if book:
            entries = [entry for entry in catalog.entries if operator_filter.matches(entry)]
            cards = [OperatorCard.from_entry(entry, owned_by_id.get(entry.char_id), equipment_map) for entry in entries]
        else:
            cards = []
            for character in characters:
                entry = catalog.by_id.get(character.charId) or OperatorCatalogEntry.fallback(character.charId)
                if operator_filter.matches(entry):
                    cards.append(OperatorCard.from_entry(entry, character, equipment_map))
            cards.sort(key=lambda card: (-card.sort_id, card.char_id))
        return cls(status=status, filter=operator_filter, cards=cards, book=book)

    @property
    def title(self) -> str:
        return "Operator Book" if self.book else "Operator Box"

    @property
    def tags(self) -> list[str]:
        return ["图鉴" if self.book else "持有", *self.filter.tags]

    @property
    def summary(self) -> str:
        return " · ".join(self.tags)

    def with_cards(self, cards: list[OperatorCard]) -> "OperatorRoster":
        return type(self)(status=self.status, filter=self.filter, cards=cards, book=self.book)
