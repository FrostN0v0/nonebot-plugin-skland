from datetime import datetime, timedelta

from pydantic import AnyUrl as Url
from nonebot_plugin_htmlrender import template_to_pic

from .schemas import ArkCard
from .config import RES_DIR, TEMPLATES_DIR


async def render_ark_card(props: ArkCard, bg: str | Url) -> bytes:
    register_time = datetime.fromtimestamp(props.status.registerTs).strftime("%Y-%m-%d")
    main_progress = props.status.mainStageProgress if props.status.mainStageProgress else "全部完成"
    for char in props.assistChars:
        if char.equip:
            if char.equip.id in props.equipmentInfoMap.keys():
                equip_id = props.equipmentInfoMap[char.equip.id].typeIcon
                uniequip_path = RES_DIR / "images" / "ark_card" / "uniequip" / f"{equip_id}.png"
                char.uniequip = uniequip_path.as_uri()
        else:
            uniequip_path = RES_DIR / "images" / "ark_card" / "uniequip" / "original.png"
            char.uniequip = uniequip_path.as_uri()
    stoke_max = 0
    stoke_count = 0
    for manufacture in props.building.manufactures:
        if manufacture.formulaId in props.manufactureFormulaInfoMap.keys():
            formula_weight = props.manufactureFormulaInfoMap[manufacture.formulaId].weight
            stoke_max += int(manufacture.capacity / formula_weight)
            elapsed_time = datetime.now().timestamp() - manufacture.lastUpdateTime
            cost_time = props.manufactureFormulaInfoMap[manufacture.formulaId].costPoint / manufacture.speed
            additional_complete = round(elapsed_time / cost_time)
            if datetime.now().timestamp() >= manufacture.completeWorkTime:
                stoke_count += manufacture.capacity // formula_weight
            else:
                to_be_processed = (manufacture.completeWorkTime - manufacture.lastUpdateTime) / (
                    cost_time / manufacture.speed
                )
                has_processed = to_be_processed - int(to_be_processed)
                additional_complete = (elapsed_time - has_processed * cost_time) / cost_time
                stoke_count += manufacture.complete + int(additional_complete) + 1

    trainee_char_id = props.building.training.trainee.charId if props.building.training.trainee else ""
    if trainee_char_id in props.charInfoMap.keys():
        trainee_char_name = props.charInfoMap[trainee_char_id].name
    else:
        trainee_char_name = ""

    ap_recovery_time = format_timestamp(props.status.ap.completeRecoveryTime - datetime.now().timestamp())
    if props.status.ap.completeRecoveryTime > datetime.now().timestamp():
        ap_recovery = f"{ap_recovery_time}后全部恢复"
    else:
        ap_recovery = "已全部恢复"

    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="ark_card.html.jinja2",
        templates={
            "background_image": bg,
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
            "labor": props.building.labor,
            "rested": props.building.rested_chars,
            "dorm_chars": props.building.dorm_chars,
            "trading_stoke": props.building.trading_stock,
            "trading_stoke_limit": props.building.trading_stock_limit,
            "manu_stoke_max": stoke_max,
            "manu_stoke_count": stoke_count,
            "tired": len(props.building.tiredChars),
            "clue": props.building.meeting.clue,
            "ap": props.status.ap,
            "ap_recovery": ap_recovery,
            "recruit_finished": props.recruit_finished,
            "recruit_max": len(props.recruit),
            "recruit_complete_time": props.recruit_complete_time,
            "refresh_count": props.building.hire.refreshCount,
            "refresh_complete_time": props.building.hire.refresh_complete_time,
            "campaign": props.campaign,
            "weekly_refresh": time_to_next_monday_4am(),
            "daily_refresh": time_to_next_4am(),
            "routine": props.routine,
            "tower": props.tower.reward,
            "tower_refresh": format_timestamp(props.tower.reward.termTs - datetime.now().timestamp()),
            "training_char": trainee_char_name,
            "training_state": props.building.training.training_state,
            "training_complete_time": format_timestamp(props.building.training.remainSecs),
        },
        pages={
            "viewport": {"width": 706, "height": 1160},
            "base_url": f"file://{TEMPLATES_DIR}",
        },
    )


def format_timestamp(timestamp: float) -> str:
    delta = timedelta(seconds=timestamp)
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes = remainder // 60

    if days > 0:
        return f"{days}天{hours}小时{minutes}分钟"
    elif hours > 0:
        return f"{hours}小时{minutes}分钟"
    else:
        return f"{minutes}分钟"


def time_to_next_monday_4am():
    now = datetime.now()
    days_until_monday = (7 - now.weekday()) % 7
    next_monday = now + timedelta(days=days_until_monday)
    next_monday_4am = next_monday.replace(hour=4, minute=0, second=0, microsecond=0)
    if now > next_monday_4am:
        next_monday_4am += timedelta(weeks=1)

    return format_timestamp(next_monday_4am.timestamp() - now.timestamp())


def time_to_next_4am():
    now = datetime.now()
    next_4am = now.replace(hour=4, minute=0, second=0, microsecond=0)
    if now > next_4am:
        next_4am += timedelta(days=1)
    return format_timestamp(next_4am.timestamp() - now.timestamp())
