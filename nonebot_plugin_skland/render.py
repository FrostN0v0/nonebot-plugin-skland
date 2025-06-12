from datetime import datetime

from pydantic import AnyUrl as Url
from nonebot_plugin_htmlrender import template_to_pic

from .config import TEMPLATES_DIR
from .schemas import ArkCard, RogueData
from .filters import (
    loads_json,
    format_timestamp,
    time_to_next_4am,
    charId_to_avatarUrl,
    format_timestamp_str,
    charId_to_portraitUrl,
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
