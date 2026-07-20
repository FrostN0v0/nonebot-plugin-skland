"""Arknights operator roster helpers for box / book commands."""

from __future__ import annotations

import json
import hashlib
from urllib.parse import quote
from functools import lru_cache
from dataclasses import dataclass

from nonebot import logger

from .config import RES_DIR, CACHE_DIR
from .schemas.arknights.models.assist_chars import Equipment
from .schemas.arknights.models.chars import Character as OwnedChar

MEDIA = "https://media.prts.wiki"
CATALOG_PATH = RES_DIR / "data" / "char_catalog.json"

PROFESSION_ALIASES: dict[str, str] = {
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
    "warrior": "近卫",
    "tank": "重装",
    "sniper": "狙击",
    "caster": "术师",
    "medic": "医疗",
    "support": "辅助",
    "special": "特种",
    "vanguard": "先锋",
    "guard": "近卫",
    "defender": "重装",
}

UHS_URL = f"{MEDIA}/7/7f/干员图鉴_uh_阴影.png"
UH_URL = {
    0: f"{MEDIA}/6/68/干员图鉴_uh_0.png",
    1: f"{MEDIA}/d/d7/干员图鉴_uh_1.png",
    2: f"{MEDIA}/6/69/干员图鉴_uh_2.png",
    3: f"{MEDIA}/e/e5/干员图鉴_uh_3.png",
    4: f"{MEDIA}/9/92/干员图鉴_uh_4.png",
    5: f"{MEDIA}/4/45/干员图鉴_uh_5.png",
}
LH_URL = {
    0: f"{MEDIA}/0/0b/干员图鉴_lh_0%2C1%2C2.png",
    1: f"{MEDIA}/0/0b/干员图鉴_lh_0%2C1%2C2.png",
    2: f"{MEDIA}/0/0b/干员图鉴_lh_0%2C1%2C2.png",
    3: f"{MEDIA}/a/a5/干员图鉴_lh_3.png",
    4: f"{MEDIA}/9/9e/干员图鉴_lh_4.png",
    5: f"{MEDIA}/a/a5/干员图鉴_lh_5.png",
}
LIGHT_URL = {
    0: f"{MEDIA}/a/a7/干员图鉴_稀有度_亮光_0.png",
    1: f"{MEDIA}/9/9c/干员图鉴_稀有度_亮光_1.png",
    2: f"{MEDIA}/b/b0/干员图鉴_稀有度_亮光_2.png",
    3: f"{MEDIA}/0/0d/干员图鉴_稀有度_亮光_3.png",
    4: f"{MEDIA}/f/f7/干员图鉴_稀有度_亮光_4.png",
    5: f"{MEDIA}/1/19/干员图鉴_稀有度_亮光_5.png",
}
BG_URL = {
    0: f"{MEDIA}/2/25/干员图鉴_背景_0%2C1%2C2.png",
    1: f"{MEDIA}/2/25/干员图鉴_背景_0%2C1%2C2.png",
    2: f"{MEDIA}/2/25/干员图鉴_背景_0%2C1%2C2.png",
    3: f"{MEDIA}/b/b1/干员图鉴_背景_3.png",
    4: f"{MEDIA}/a/ad/干员图鉴_背景_4.png",
    5: f"{MEDIA}/c/c9/干员图鉴_背景_5.png",
}
RARITY_URL = {
    0: f"{MEDIA}/6/62/稀有度_黄_0.png",
    1: f"{MEDIA}/0/02/稀有度_黄_1.png",
    2: f"{MEDIA}/4/4b/稀有度_黄_2.png",
    3: f"{MEDIA}/4/4c/稀有度_黄_3.png",
    4: f"{MEDIA}/8/81/稀有度_黄_4.png",
    5: f"{MEDIA}/4/46/稀有度_黄_5.png",
}


def media_url(filename: str) -> str:
    digest = hashlib.md5(filename.encode("utf-8")).hexdigest()
    return f"{MEDIA}/{digest[0]}/{digest[:2]}/{filename}"


def profession_icon_url(profession: str) -> str:
    return media_url(f"图标_职业_{profession}.png")


def logo_url(logo: str) -> str:
    if not logo:
        return ""
    return media_url(f"Logo_{logo}.png")


def skin_portrait_url(skin_id: str) -> str:
    portrait_id = skin_id
    for symbol in ("@", "#"):
        if symbol in skin_id:
            portrait_id = skin_id.replace(symbol, "_", 1)
            break
    img_path = CACHE_DIR / "portrait" / f"{portrait_id}.png"
    if img_path.exists():
        return img_path.as_uri()
    encoded = quote(skin_id, safe="")
    return f"https://web.hycdn.cn/arknights/game/assets/char_skin/portrait/{encoded}.png"


def potential_url(rank: int) -> str:
    path = RES_DIR / "images" / "ark_card" / "potential" / f"potential_{rank}.png"
    return path.as_uri() if path.exists() else ""


def elite_url(phase: int) -> str:
    path = RES_DIR / "images" / "ark_card" / "elite" / f"elite_{phase}.png"
    return path.as_uri() if path.exists() else ""


def skill_icon_url(skill_id: str) -> str:
    img_path = CACHE_DIR / "skill" / f"skill_icon_{skill_id}.png"
    if img_path.exists():
        return img_path.as_uri()
    encoded = quote(skill_id, safe="")
    return f"https://web.hycdn.cn/arknights/game/assets/char_skill/{encoded}.png"


def uniequip_icon_url(type_icon: str | None) -> str:
    icon = type_icon or "original"
    return f"https://torappu.prts.wiki/assets/uniequip_direction/{icon}.png"


def skill_level_label(main_skill_lvl: int, specialize_level: int) -> str:
    if specialize_level > 0:
        return f"专{specialize_level}"
    return str(main_skill_lvl)


def default_skin_id(char_id: str) -> str:
    return f"{char_id}#1"


@dataclass(frozen=True)
class CatalogModule:
    id: str
    type_icon: str


@dataclass(frozen=True)
class CatalogEntry:
    char_id: str
    name: str
    appellation: str
    profession: str
    rarity: int  # 0-based (5 == 6-star)
    sort_id: int
    logo: str
    skill_ids: tuple[str, ...] = ()
    modules: tuple[CatalogModule, ...] = ()

    @property
    def star(self) -> int:
        return self.rarity + 1


@dataclass(frozen=True)
class RosterSkill:
    icon: str
    specialize_level: int
    main_skill_lvl: int

    @property
    def mastered(self) -> bool:
        return self.specialize_level >= 3


@dataclass(frozen=True)
class RosterModule:
    icon: str
    level: int
    selected: bool
    locked: bool = False


@dataclass
class RosterCard:
    char_id: str
    name: str
    profession: str
    rarity: int
    sort_id: int
    owned: bool
    skin_id: str
    portrait: str
    uh: str
    uhs: str
    class_icon: str
    rarity_icon: str
    lh: str
    light: str
    bg: str
    logo: str
    potential: str
    elite: str
    level_text: str
    meta_text: str
    skills: list[RosterSkill]
    modules: list[RosterModule]


@dataclass(frozen=True)
class RosterFilter:
    stars: frozenset[int]  # 1-6 display stars
    professions: frozenset[str]  # CN profession names; empty = all
    name: str = ""

    def match(self, entry: CatalogEntry) -> bool:
        if self.stars and entry.star not in self.stars:
            return False
        if self.professions and entry.profession not in self.professions:
            return False
        if self.name:
            q = self.name.casefold()
            haystacks = (
                entry.name.casefold(),
                entry.appellation.casefold(),
                entry.char_id.casefold(),
            )
            if all(q not in text for text in haystacks):
                return False
        return True


def parse_stars(raw: str | None) -> frozenset[int]:
    """Parse user rarity input. Default: {6}. Use 'all' / '*' for 1-6."""
    if raw is None or not str(raw).strip():
        return frozenset({6})
    text = str(raw).strip().lower()
    if text in {"all", "*", "a", "全部"}:
        return frozenset(range(1, 7))
    stars: set[int] = set()
    for part in text.replace("，", ",").replace(" ", ",").replace("~", "-").split(","):
        part = part.strip()
        if not part:
            continue
        if part.endswith("星"):
            part = part[:-1]
        if "-" in part:
            left, _, right = part.partition("-")
            try:
                lo, hi = int(left), int(right)
            except ValueError as e:
                raise ValueError(f"invalid rarity: {raw}") from e
            if lo > hi:
                lo, hi = hi, lo
            if lo < 1 or hi > 6:
                raise ValueError(f"rarity out of range 1-6: {part}")
            stars.update(range(lo, hi + 1))
            continue
        try:
            value = int(part)
        except ValueError as e:
            raise ValueError(f"invalid rarity: {raw}") from e
        if value < 1 or value > 6:
            raise ValueError(f"rarity out of range 1-6: {value}")
        stars.add(value)
    return frozenset(stars) if stars else frozenset({6})


def parse_professions(raw: str | None) -> frozenset[str]:
    if raw is None or not str(raw).strip():
        return frozenset()
    result: set[str] = set()
    for part in str(raw).replace("，", ",").replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        key = PROFESSION_ALIASES.get(part) or PROFESSION_ALIASES.get(part.casefold())
        if not key:
            raise ValueError(f"unknown profession: {part}")
        result.add(key)
    return frozenset(result)


@lru_cache(maxsize=1)
def load_catalog() -> tuple[CatalogEntry, ...]:
    if not CATALOG_PATH.exists():
        logger.error(f"char catalog missing: {CATALOG_PATH}")
        return ()
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    entries = [
        CatalogEntry(
            char_id=item["char_id"],
            name=item["name"],
            appellation=item.get("appellation") or "",
            profession=item["profession"],
            rarity=int(item["rarity"]),
            sort_id=int(item["sort_id"]),
            logo=item.get("logo") or "",
            skill_ids=tuple(sid for sid in (item.get("skills") or []) if sid),
            modules=tuple(
                CatalogModule(id=m["id"], type_icon=m.get("type_icon") or "original")
                for m in (item.get("modules") or [])
                if m.get("id")
            ),
        )
        for item in data
    ]
    return tuple(sorted(entries, key=lambda e: (-e.sort_id, e.char_id)))


def catalog_by_id() -> dict[str, CatalogEntry]:
    return {e.char_id: e for e in load_catalog()}


def chrome_for_rarity(rarity: int) -> dict[str, str]:
    r = max(0, min(5, rarity))
    return {
        "uh": UH_URL[r],
        "uhs": UHS_URL,
        "rarity_icon": RARITY_URL[r],
        "lh": LH_URL[r],
        "light": LIGHT_URL[r],
        "bg": BG_URL[r],
    }


def build_skills(entry: CatalogEntry, owned: OwnedChar | None) -> list[RosterSkill]:
    if owned is not None and owned.skills:
        return [
            RosterSkill(
                icon=skill_icon_url(skill.id),
                specialize_level=max(0, min(3, skill.specializeLevel)),
                main_skill_lvl=owned.mainSkillLvl,
            )
            for skill in owned.skills
            if skill.id
        ]
    return [
        RosterSkill(icon=skill_icon_url(skill_id), specialize_level=0, main_skill_lvl=0) for skill_id in entry.skill_ids
    ]


def build_modules(
    entry: CatalogEntry,
    owned: OwnedChar | None,
    equipment_map: dict[str, Equipment] | None = None,
) -> list[RosterModule]:
    equipment_map = equipment_map or {}
    owned_by_id = {eq.id: eq for eq in owned.equip} if owned is not None else {}

    def resolve_type_icon(module_id: str, fallback: str) -> str:
        info = equipment_map.get(module_id)
        if info and info.typeIcon:
            return info.typeIcon
        return fallback or "original"

    # Canonical slots from catalog (operator-specific count + icons).
    # Skip default certificate modules (typeIcon == original).
    if entry.modules:
        modules: list[RosterModule] = []
        for catalog_mod in entry.modules:
            if (catalog_mod.type_icon or "original") == "original":
                continue
            type_icon = resolve_type_icon(catalog_mod.id, catalog_mod.type_icon)
            eq = owned_by_id.get(catalog_mod.id)
            if owned is None or eq is None:
                modules.append(
                    RosterModule(
                        icon=uniequip_icon_url(type_icon),
                        level=0,
                        selected=False,
                        locked=True,
                    )
                )
                continue
            locked = bool(eq.locked)
            modules.append(
                RosterModule(
                    icon=uniequip_icon_url(type_icon),
                    level=eq.level,
                    selected=(not locked) and bool(owned.defaultEquipId and eq.id == owned.defaultEquipId),
                    locked=locked,
                )
            )
        return modules

    # Fallback when catalog has no module rows for this char.
    if owned is None:
        return []
    modules = []
    for eq in owned.equip:
        type_icon = resolve_type_icon(eq.id, "original")
        if type_icon == "original":
            continue
        locked = bool(eq.locked)
        modules.append(
            RosterModule(
                icon=uniequip_icon_url(type_icon),
                level=eq.level,
                selected=(not locked) and bool(owned.defaultEquipId and eq.id == owned.defaultEquipId),
                locked=locked,
            )
        )
    return modules


def build_card(
    entry: CatalogEntry,
    owned: OwnedChar | None,
    *,
    equipment_map: dict[str, Equipment] | None = None,
    force_owned_style: bool = False,
) -> RosterCard:
    is_owned = owned is not None
    if is_owned and owned is not None:
        skin_id = owned.skinId or default_skin_id(entry.char_id)
        meta = f"Lv{owned.level}"
        pot = potential_url(owned.potentialRank)
        elite = elite_url(owned.evolvePhase)
        level_text = str(owned.level)
        logo = pot or logo_url(entry.logo)
    else:
        skin_id = default_skin_id(entry.char_id)
        meta = ""
        pot = ""
        elite = ""
        level_text = ""
        logo = logo_url(entry.logo)

    chrome = chrome_for_rarity(entry.rarity)
    return RosterCard(
        char_id=entry.char_id,
        name=entry.name,
        profession=entry.profession,
        rarity=entry.rarity,
        sort_id=entry.sort_id,
        owned=is_owned or force_owned_style,
        skin_id=skin_id,
        portrait=skin_portrait_url(skin_id),
        uh=chrome["uh"],
        uhs=chrome["uhs"],
        class_icon=profession_icon_url(entry.profession),
        rarity_icon=chrome["rarity_icon"],
        lh=chrome["lh"],
        light=chrome["light"],
        bg=chrome["bg"],
        logo=logo,
        potential=pot,
        elite=elite,
        level_text=level_text,
        meta_text=meta,
        skills=build_skills(entry, owned),
        modules=build_modules(entry, owned, equipment_map),
    )


def build_box_cards(
    owned_chars: list[OwnedChar],
    filt: RosterFilter,
    equipment_map: dict[str, Equipment] | None = None,
) -> list[RosterCard]:
    index = catalog_by_id()
    cards: list[RosterCard] = []
    for ch in owned_chars:
        entry = index.get(ch.charId)
        if entry is None:
            # Fallback for chars missing from catalog snapshot.
            entry = CatalogEntry(
                char_id=ch.charId,
                name=ch.charId,
                appellation="",
                profession="",
                rarity=5,
                sort_id=0,
                logo="",
            )
            if filt.stars and entry.star not in filt.stars:
                continue
            if filt.professions:
                continue
            if filt.name and filt.name.casefold() not in ch.charId.casefold():
                continue
        elif not filt.match(entry):
            continue
        cards.append(build_card(entry, ch, equipment_map=equipment_map))
    cards.sort(key=lambda c: (-c.sort_id, c.char_id))
    return cards


def build_book_cards(
    owned_chars: list[OwnedChar],
    filt: RosterFilter,
    equipment_map: dict[str, Equipment] | None = None,
) -> list[RosterCard]:
    owned_map = {c.charId: c for c in owned_chars}
    cards: list[RosterCard] = []
    for entry in load_catalog():
        if not filt.match(entry):
            continue
        cards.append(build_card(entry, owned_map.get(entry.char_id), equipment_map=equipment_map))
    return cards


def filter_summary(filt: RosterFilter) -> str:
    if filt.stars == frozenset(range(1, 7)):
        stars = "全部"
    else:
        stars = ",".join(str(s) for s in sorted(filt.stars, reverse=True)) + "星"
    prof = "全部职业" if not filt.professions else ",".join(sorted(filt.professions))
    name = f" · 名称含「{filt.name}」" if filt.name else ""
    return f"{stars} · {prof}{name}"
