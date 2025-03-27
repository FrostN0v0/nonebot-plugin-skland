from nonebot_plugin_htmlrender import template_to_pic

from .schemas import ArkCard
from .config import RES_DIR, TEMPLATES_DIR
from .utils import format_time_from_timestamp


async def render_ark_card(props: ArkCard) -> bytes:
    register_time = format_time_from_timestamp(props.status.registerTs)
    main_progress = props.status.mainStageProgress if props.status.mainStageProgress else "全部完成"
    for char in props.assistChars:
        if char.equip.id in props.equipmentInfoMap.keys():
            equip_id = props.equipmentInfoMap[char.equip.id].typeIcon
            uniequip_path = RES_DIR / "images" / "ark_card" / "uniequip" / f"{equip_id}.png"
            char.uniequip = uniequip_path.as_uri()
    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="ark_card.html.jinja2",
        templates={
            "Dr_name": props.status.name,
            "Dr_level": props.status.level,
            "Dr_avatar": props.status.avatar.url,
            "register_time": register_time,
            "main_progress": main_progress,
            "employed_chars": len(props.chars),
            "skins": len(props.skins),
            "furniture": props.building.furniture.total,
            "medals": props.medal.total,
            "assist_chars": props.assistChars,
        },
        pages={
            "viewport": {"width": 706, "height": 1160},
            "base_url": f"file://{TEMPLATES_DIR}",
        },
    )
