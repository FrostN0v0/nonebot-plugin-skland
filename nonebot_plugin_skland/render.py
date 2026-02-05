from datetime import datetime

from pydantic import AnyUrl as Url
from nonebot_plugin_htmlrender import template_to_pic

from .model import Character
from .config import RES_DIR, TEMPLATES_DIR, config
from .schemas import Clue, Status, ArkCard, RogueData, EndfieldCard, GroupedGachaRecord
from .filters import (
    loads_json,
    format_date_ymd,
    get_domain_info,
    format_timestamp,
    get_rarity_color,
    time_to_next_4am,
    get_property_icon,
    charId_to_avatarUrl,
    format_stamina_time,
    format_timestamp_md,
    get_profession_icon,
    format_timestamp_str,
    charId_to_portraitUrl,
    get_equip_rarity_color,
    time_to_next_monday_4am,
)


async def render_ark_card(props: ArkCard, bg: str | Url) -> bytes:
    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="ark_card.html.jinja2",
        templates={
            "now_ts": datetime.now().timestamp(),
            "background_image": bg,
            "status": props.status,
            "employed_chars": len(props.chars),
            "skins": len(props.skins),
            "building": props.building,
            "medals": props.medal.total,
            "assist_chars": props.assistChars,
            "recruit_finished": props.recruit_finished,
            "recruit_max": len(props.recruit),
            "recruit_complete_time": props.recruit_complete_time,
            "campaign": props.campaign,
            "routine": props.routine,
            "tower": props.tower,
            "training_char": props.trainee_char,
        },
        filters={
            "format_timestamp": format_timestamp,
            "time_to_next_4am": time_to_next_4am,
            "time_to_next_monday_4am": time_to_next_monday_4am,
        },
        pages={
            "viewport": {"width": 706, "height": 1160},
            "base_url": f"file://{TEMPLATES_DIR}",
        },
    )


async def render_rogue_card(props: RogueData, bg: str | Url) -> bytes:
    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="rogue.html.jinja2",
        templates={
            "background_image": bg,
            "topic_img": props.topic_img,
            "topic": props.topic,
            "now_ts": datetime.now().timestamp(),
            "career": props.career,
            "game_user_info": props.gameUserInfo,
            "history": props.history,
        },
        filters={
            "format_timestamp_str": format_timestamp_str,
            "charId_to_avatarUrl": charId_to_avatarUrl,
            "charId_to_portraitUrl": charId_to_portraitUrl,
        },
        pages={
            "viewport": {"width": 2200, "height": 1},
            "base_url": f"file://{TEMPLATES_DIR}",
        },
        device_scale_factor=1.5,
    )


async def render_rogue_info(props: RogueData, bg: str | Url, id: int, is_favored: bool) -> bytes:
    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="rogue_info.html.jinja2",
        templates={
            "id": id,
            "record": props.history.favourRecords[id - 1]
            if is_favored and id - 1 < len(props.history.favourRecords)
            else (props.history.records[id - 1] if id - 1 < len(props.history.records) else None),
            "is_favored": is_favored,
            "background_image": bg,
            "topic_img": props.topic_img,
            "topic": props.topic,
            "now_ts": datetime.now().timestamp(),
            "career": props.career,
            "game_user_info": props.gameUserInfo,
            "history": props.history,
        },
        filters={
            "format_timestamp_str": format_timestamp_str,
            "charId_to_avatarUrl": charId_to_avatarUrl,
            "charId_to_portraitUrl": charId_to_portraitUrl,
            "loads_json": loads_json,
        },
        pages={
            "viewport": {"width": 1100, "height": 1},
            "base_url": f"file://{TEMPLATES_DIR}",
        },
        device_scale_factor=1.5,
    )


async def render_clue_board(props: Clue):
    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="clue.html.jinja2",
        templates={
            "clue": props,
        },
        pages={
            "viewport": {"width": 1100, "height": 1},
            "base_url": f"file://{TEMPLATES_DIR}",
        },
        device_scale_factor=1.5,
    )


async def render_gacha_history(
    props: GroupedGachaRecord, char: Character, status: Status, begin: int | None = None, limit: int | None = None
) -> bytes:
    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="gacha.html.jinja2",
        templates={
            "record": props,
            "character": char,
            "status": status,
            "start_index": begin,
            "end_index": limit,
        },
        filters={
            "format_timestamp_md": format_timestamp_md,
        },
        pages={
            "viewport": {"width": 720, "height": 1},
            "base_url": f"file://{TEMPLATES_DIR}",
        },
        device_scale_factor=1.5,
    )


async def render_ef_card(props: EndfieldCard, bg: str | Url, show_all: bool = False, is_simple: bool = False) -> bytes:
    # 预处理角色列表：根据 show_all 决定是否过滤
    if show_all:
        filtered_chars = props.chars
    else:
        # 按 config.charIds 过滤并保持顺序
        char_map = {char.id: char for char in props.chars}
        filtered_chars = [char_map[cid] for cid in props.config.charIds if cid in char_map]

    # 提取总控中枢等级
    control_center_level = 0
    for room in props.spaceShip.rooms:
        if room.id == "control_center":
            control_center_level = room.level
            break

    # 汇总所有据点的 trchestCount（储藏箱总数）
    total_trchest_count = sum(collection.trchestCount for domain in props.domain for collection in domain.collections)

    # 计算理智恢复剩余时间
    current_ts = float(props.currentTs) if props.currentTs else datetime.now().timestamp()
    max_ts = float(props.dungeon.maxTs) if props.dungeon.maxTs else current_ts
    stamina_remaining_seconds = max(0, max_ts - current_ts)

    # 计算理智进度百分比
    cur_stamina = int(props.dungeon.curStamina) if props.dungeon.curStamina else 0
    max_stamina = int(props.dungeon.maxStamina) if props.dungeon.maxStamina else 1
    stamina_percent = min(100, (cur_stamina / max_stamina) * 100) if max_stamina > 0 else 0

    # Simple 背景模式：命令行参数优先于配置
    simple_bg_enabled = simple_bg or config.endfield_background_simple
    simple_bg = (RES_DIR / "images" / "background" / "endfield" / "simple" / "simple_bg.png").as_posix()
    simple_bg_top = (RES_DIR / "images" / "background" / "endfield" / "simple" / "simple_bg_top.png").as_posix()

    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="endfield_card.html.jinja2",
        templates={
            "now_ts": datetime.now().timestamp(),
            "background_image": bg,
            "simple_bg_enabled": simple_bg_enabled,
            "simple_bg": simple_bg,
            "simple_bg_top": simple_bg_top,
            "chars": filtered_chars,
            "base": props.base,
            "dungeon": props.dungeon,
            "bpSystem": props.bpSystem,
            "dailyMission": props.dailyMission,
            "achieve": props.achieve,
            "domain": props.domain,
            "control_center_level": control_center_level,
            "total_trchest_count": total_trchest_count,
            "stamina_remaining_seconds": stamina_remaining_seconds,
            "stamina_percent": stamina_percent,
        },
        filters={
            "format_timestamp": format_timestamp,
            "format_stamina_time": format_stamina_time,
            "format_date_ymd": format_date_ymd,
            "get_domain_info": get_domain_info,
            "get_rarity_color": get_rarity_color,
            "get_equip_rarity_color": get_equip_rarity_color,
            "get_profession_icon": get_profession_icon,
            "get_property_icon": get_property_icon,
        },
        pages={
            "viewport": {"width": 706, "height": 1},
            "base_url": f"file://{TEMPLATES_DIR}",
        },
    )
