from pydantic import Field, BaseModel

from . import operator_query
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
    query: operator_query.OperatorRosterQuery
    cards: list[OperatorCard] = Field(default_factory=list)

    @classmethod
    def build(
        cls,
        status: Status,
        catalog: OperatorCatalog,
        characters: list[Character],
        query: operator_query.OperatorRosterQuery,
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
    def _sort_cards(cards: list[OperatorCard], sort: operator_query.OperatorSort) -> list[OperatorCard]:
        def release_key(card: OperatorCard) -> tuple[int, str]:
            return -card.sort_id, card.char_id

        if sort is operator_query.OperatorSort.RELEASE:
            return sorted(cards, key=release_key)

        owned_cards = sorted((card for card in cards if card.character is not None), key=release_key)
        unowned_cards = sorted((card for card in cards if card.character is None), key=release_key)
        if sort is operator_query.OperatorSort.ACQUIRED:
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
