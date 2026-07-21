"""Render a sample box/book preview PNG for visual check."""

from __future__ import annotations

import asyncio
from pathlib import Path

import nonebot
from nonebot import init

# Distinct mastery rows for owned operators 0..7 (S1/S2/S3).
SKILL_SPECS: list[list[int]] = [
    [0, 0, 0],
    [1, 0, 0],
    [2, 1, 0],
    [3, 2, 1],
    [3, 3, 0],
    [3, 3, 2],
    [3, 3, 3],
    [1, 2, 3],
]

# For each owned operator: (level, locked) applied to non-original modules in order.
MODULE_STATES: list[list[tuple[int, bool]]] = [
    [(1, False)],
    [(2, False), (0, True)],
    [(3, False), (1, False)],
    [(3, False), (2, False)],
    [(1, False), (3, False)],
    [(2, False), (0, True)],
    [(3, False), (3, False)],
    [(1, False), (2, False)],
]


async def main() -> None:
    init()
    nonebot.load_from_toml("pyproject.toml")

    from nonebot_plugin_skland.schemas.arknights.models.base import Equip
    from nonebot_plugin_skland.schemas.arknights.models.chars import Skill
    from nonebot_plugin_skland.schemas.arknights.models.assist_chars import Equipment
    from nonebot_plugin_skland.render import ROSTER_PAGE_WIDTH, render_operator_roster
    from nonebot_plugin_skland.schemas.arknights.models.chars import Character as OwnedChar
    from nonebot_plugin_skland.roster import (
        RosterFilter,
        load_catalog,
        default_skin_id,
        build_book_cards,
    )

    catalog = load_catalog()
    if not catalog:
        raise RuntimeError("Operator catalog is unavailable; start the bot or run `skland sync --data` first")
    six = [c for c in catalog if c.star == 6][:24]
    equipment_map: dict[str, Equipment] = {}
    for entry in six:
        for mod in entry.modules:
            equipment_map[mod.id] = Equipment(id=mod.id, name=mod.id, typeIcon=mod.type_icon)

    def owned_for(
        entry,
        *,
        index: int,
        level: int,
        elite: int,
        pot: int,
    ) -> OwnedChar:
        specs = SKILL_SPECS[index % len(SKILL_SPECS)]
        skill_ids = list(entry.skill_ids)[:3]
        skills = [Skill(id=sid, specializeLevel=specs[i] if i < len(specs) else 0) for i, sid in enumerate(skill_ids)]

        mod_states = MODULE_STATES[index % len(MODULE_STATES)]
        equips: list[Equip] = []
        default_equip = ""
        real_i = 0
        for mod in entry.modules:
            if (mod.type_icon or "original") == "original":
                equips.append(Equip(id=mod.id, level=1, locked=False))
                continue
            lvl, locked = mod_states[real_i] if real_i < len(mod_states) else (1, True)
            real_i += 1
            equips.append(Equip(id=mod.id, level=lvl, locked=locked))
            if not locked and not default_equip:
                default_equip = mod.id

        return OwnedChar(
            charId=entry.char_id,
            skinId=default_skin_id(entry.char_id),
            level=level,
            evolvePhase=elite,
            potentialRank=pot,
            mainSkillLvl=7 if any(s > 0 for s in specs) else max(1, 4 + index % 4),
            skills=skills,
            equip=equips,
            favorPercent=100,
            defaultSkillId="",
            gainTime=0,
            defaultEquipId=default_equip,
        )

    owned_list = [owned_for(c, index=i, level=80 + i, elite=min(2, i), pot=i % 6) for i, c in enumerate(six[:8])]
    allow = {c.char_id for c in six}
    cards = [
        c
        for c in build_book_cards(
            owned_list,
            RosterFilter(stars=frozenset({6}), professions=frozenset()),
            equipment_map=equipment_map,
        )
        if c.char_id in allow
    ][:24]

    img = await render_operator_roster(
        title="Operator Book (preview)",
        subtitle="varied skill mastery + module levels",
        cards=cards,
        page_width=ROSTER_PAGE_WIDTH,
    )
    out = Path("docs/box_book_preview.png")
    out.write_bytes(img)


if __name__ == "__main__":
    asyncio.run(main())
