from datetime import datetime, timedelta

from pydantic import AnyUrl as Url
from nonebot_plugin_htmlrender import template_to_pic

from .schemas import ArkCard
from .config import RES_DIR, TEMPLATES_DIR


async def render_ark_card(props: ArkCard, bg: str | Url) -> bytes:
    now_ts = datetime.now().timestamp()
    register_time = datetime.fromtimestamp(props.status.registerTs).strftime("%Y-%m-%d")
    main_progress = props.status.mainStageProgress if props.status.mainStageProgress else "全部完成"
    process_char_equipment(props)
    manufacture_stoke_max, manufacture_stoke_count = process_manufacture(props)
    trainee_char_name = process_trainee_char(props)

    ap_recovery_time = format_timestamp(props.status.ap.completeRecoveryTime - now_ts)
    if props.status.ap.completeRecoveryTime > now_ts:
        ap_recovery = f"{ap_recovery_time}后全部恢复"
    else:
        ap_recovery = "已全部恢复"

    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="ark_card.html.jinja2",
        templates={
            "background_image": bg,
            "status": props.status,
            "ap_recovery": ap_recovery,
            "register_time": register_time,
            "main_progress": main_progress,
            "employed_chars": len(props.chars),
            "skins": len(props.skins),
            "building": props.building,
            "medals": props.medal.total,
            "assist_chars": props.assistChars,
            "manu_stoke_max": manufacture_stoke_max,
            "manu_stoke_count": manufacture_stoke_count,
            "recruit_finished": props.recruit_finished,
            "recruit_max": len(props.recruit),
            "recruit_complete_time": props.recruit_complete_time,
            "campaign": props.campaign,
            "weekly_refresh": time_to_next_monday_4am(now_ts),
            "daily_refresh": time_to_next_4am(now_ts),
            "routine": props.routine,
            "tower": props.tower.reward,
            "tower_refresh": format_timestamp(props.tower.reward.termTs - now_ts),
            "training_char": trainee_char_name,
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


def time_to_next_monday_4am(now_ts: float) -> str:
    now = datetime.fromtimestamp(now_ts)
    days_until_monday = (7 - now.weekday()) % 7
    next_monday = now + timedelta(days=days_until_monday)
    next_monday_4am = next_monday.replace(hour=4, minute=0, second=0, microsecond=0)
    if now > next_monday_4am:
        next_monday_4am += timedelta(weeks=1)
    return format_timestamp((next_monday_4am - now).total_seconds())


def time_to_next_4am(now_ts: float) -> str:
    now = datetime.fromtimestamp(now_ts)
    next_4am = now.replace(hour=4, minute=0, second=0, microsecond=0)
    if now > next_4am:
        next_4am += timedelta(days=1)
    return format_timestamp((next_4am - now).total_seconds())


def process_char_equipment(props: ArkCard) -> None:
    for char in props.assistChars:
        if char.equip:
            if char.equip.id in props.equipmentInfoMap.keys():
                equip_id = props.equipmentInfoMap[char.equip.id].typeIcon
                uniequip_path = RES_DIR / "images" / "ark_card" / "uniequip" / f"{equip_id}.png"
                char.uniequip = uniequip_path.as_uri()
        else:
            uniequip_path = RES_DIR / "images" / "ark_card" / "uniequip" / "original.png"
            char.uniequip = uniequip_path.as_uri()


def process_manufacture(props: ArkCard) -> tuple[int, int]:
    stoke_max = 0
    stoke_count = 0
    for manu in props.building.manufactures:
        if manu.formulaId in props.manufactureFormulaInfoMap.keys():
            formula_weight = props.manufactureFormulaInfoMap[manu.formulaId].weight
            stoke_max += int(manu.capacity / formula_weight)
            elapsed_time = datetime.now().timestamp() - manu.lastUpdateTime
            cost_time = props.manufactureFormulaInfoMap[manu.formulaId].costPoint / manu.speed
            additional_complete = round(elapsed_time / cost_time)
            if datetime.now().timestamp() >= manu.completeWorkTime:
                stoke_count += manu.capacity // formula_weight
            else:
                to_be_processed = (manu.completeWorkTime - manu.lastUpdateTime) / (cost_time / manu.speed)
                has_processed = to_be_processed - int(to_be_processed)
                additional_complete = (elapsed_time - has_processed * cost_time) / cost_time
                stoke_count += manu.complete + int(additional_complete) + 1
    return stoke_max, stoke_count


def process_trainee_char(props: ArkCard) -> str:
    trainee_char = ""
    if props.building.training.training_state == "training":
        trainee_char_id = props.building.training.trainee.charId if props.building.training.trainee else ""
        if trainee_char_id in props.charInfoMap.keys():
            trainee_char = props.charInfoMap[trainee_char_id].name
    return trainee_char
