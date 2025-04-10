from datetime import datetime

from pydantic import AnyUrl as Url
from nonebot_plugin_htmlrender import template_to_pic

from .schemas import ArkCard
from .config import TEMPLATES_DIR
from .filters import format_timestamp, time_to_next_4am, time_to_next_monday_4am


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
