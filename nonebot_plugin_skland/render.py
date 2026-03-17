from datetime import datetime

from pydantic import AnyUrl as Url
from nonebot_plugin_htmlrender import template_to_pic

from .model import Character
from .config import RES_DIR, TEMPLATES_DIR, config
from .schemas import (
    Clue,
    Status,
    ArkCard,
    RogueData,
    PlayerBase,
    EndfieldCard,
    GroupedGachaRecord,
    EfGroupedGachaRecord,
)
from .filters import (
    loads_json,
    format_date_ymd,
    get_domain_info,
    format_money_wan,
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
    ef_charId_to_avatarUrl,
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
            "charId_to_avatarUrl": charId_to_avatarUrl,
            "format_timestamp_md": format_timestamp_md,
        },
        pages={
            "viewport": {"width": 720, "height": 1},
            "base_url": f"file://{TEMPLATES_DIR}",
        },
        device_scale_factor=1.5,
    )


async def render_ef_gacha_history(
    props: EfGroupedGachaRecord,
    player: PlayerBase,
    char: Character,
    begin: int | None = None,
    limit: int | None = None,
) -> bytes:
    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="ef_gacha.html.jinja2",
        templates={
            "avatar_url": player.avatarUrl,
            "record": props,
            "character": char,
            "start_index": begin,
            "end_index": limit,
        },
        filters={
            "format_timestamp_md": format_timestamp_md,
            "ef_charId_to_avatarUrl": ef_charId_to_avatarUrl,
        },
        pages={
            "viewport": {"width": 800, "height": 1},
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
        if room.type == 0:
            control_center_level = room.level
            break

    # 汇总所有据点的 trchestCount（储藏箱总数）
    total_trchest_count = sum(collection.trchestCount for domain in props.domain for collection in domain.collections)
    # 汇总所有据点的 puzzleCount（醚质总数）
    total_puzzle_count = sum(collection.puzzleCount for domain in props.domain for collection in domain.collections)
    # 计算理智恢复剩余时间
    current_ts = float(props.currentTs) if props.currentTs else datetime.now().timestamp()
    max_ts = float(props.dungeon.maxTs) if props.dungeon.maxTs else current_ts
    stamina_remaining_seconds = max(0, max_ts - current_ts)

    # 计算理智进度百分比
    cur_stamina = int(props.dungeon.curStamina) if props.dungeon.curStamina else 0
    max_stamina = int(props.dungeon.maxStamina) if props.dungeon.maxStamina else 1
    stamina_percent = min(100, (cur_stamina / max_stamina) * 100) if max_stamina > 0 else 0

    # Simple 背景模式：命令行参数优先于配置
    simple_bg_enabled = is_simple or config.endfield_background_simple
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
            "weeklyMission": props.weeklyMission,
            "achieve": props.achieve,
            "domain": props.domain,
            "control_center_level": control_center_level,
            "total_trchest_count": total_trchest_count,
            "total_puzzle_count": total_puzzle_count,
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
            "format_money_wan": format_money_wan,
            "get_property_icon": get_property_icon,
        },
        pages={
            "viewport": {"width": 706, "height": 1},
            "base_url": f"file://{TEMPLATES_DIR}",
        },
    )


async def render_help_menu(extra_data: dict, bg: str | Url) -> bytes:
    menu = [
        {"name": "扫码绑定", "desc": "森空岛扫码绑定"},
        {"name": "森空岛解绑", "desc": "解绑森空岛账号"},
        {"name": "skland", "desc": "查询明日方舟角色信息卡片"},
        {"name": "明日方舟签到", "desc": "签到绑定的明日方舟账号。"},
        {"name": "签到详情", "desc": "查看绑定角色的自动签到状态。"},
        {"name": "全体签到", "desc": "签到所有绑定到bot的明日方舟账号。"},
        {"name": "全体签到详情", "desc": "查看所有绑定角色的签到状态。"},
        {"name": "终末地签到", "desc": "签到绑定的终末地账号。"},
        {"name": "终末地签到详情", "desc": "查看绑定角色的终末地自动签到状态。"},
        {"name": "终末地全体签到", "desc": "签到所有绑定到bot的终末地账号。"},
        {"name": "终末地全体签到详情", "desc": "查看所有绑定角色的终末地签到状态。"},
        {"name": "终末地角色卡片", "desc": "查询终末地角色信息卡片。"},
        {"name": "<傀影|水月|萨米|萨卡兹|界园>肉鸽", "desc": "查询指定主题的肉鸽战绩。"},
        {"name": "战绩详情", "desc": "查询单局肉鸽战绩详情。"},
        {"name": "方舟抽卡记录", "desc": "查询绑定到bot的明日方舟账号的抽卡记录。"},
        {"name": "终末地抽卡记录", "desc": "查询绑定到bot的终末地账号的抽卡记录。"},
        {"name": "终末地抽卡更新", "desc": "从接口拉取最新终末地抽卡记录并更新数据库。"},
        {"name": "导入抽卡记录", "desc": "导入小黑盒明日方舟抽卡记录。"},
        {"name": "角色更新", "desc": "同步森空岛绑定的游戏角色信息。"},
        {"name": "全体角色更新", "desc": "更新所有绑定用户的角色信息。"},
        {"name": "资源更新", "desc": "更新游戏资源（图片和数据）。"},
    ]

    import math

    total = len(menu)
    per_col = math.ceil(total / 3)

    column1 = menu[0:per_col]
    column2 = menu[per_col : per_col * 2]
    column3 = menu[per_col * 2 :]

    # 然后将 column1, column2, column3 传给渲染函数
    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="help.html.jinja2",
        templates={
            "now_ts": datetime.now().timestamp(),
            "background_image": bg,
            "column1": column1,
            "column2": column2,
            "column3": column3,
        },
        filters={},
        pages={
            "viewport": {"width": 706, "height": 1},
            "base_url": f"file://{TEMPLATES_DIR}",
        },
    )
