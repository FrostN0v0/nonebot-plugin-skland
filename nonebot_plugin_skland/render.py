from datetime import datetime

from pydantic import AnyUrl as Url

from .image_cache import wait_for_page_resources
from .config import RES_DIR, TEMPLATES_DIR, config
from .compact import open_html_page, template_to_html
from .image_cache import cached_template_to_pic as template_to_pic
from .schemas import (
    Clue,
    Status,
    ArkCard,
    RogueData,
    EfGachaView,
    EndfieldCard,
    WarEchoesView,
    BoundRolesCard,
    OperatorRoster,
    GroupedGachaRecord,
)
from .filters import (
    loads_json,
    format_date_ymd,
    get_domain_info,
    format_money_wan,
    format_timestamp,
    get_rarity_color,
    time_to_next_4am,
    war_echoes_asset,
    get_property_icon,
    charId_to_avatarUrl,
    format_stamina_time,
    format_timestamp_md,
    get_profession_icon,
    format_timestamp_str,
    charId_to_portraitUrl,
    ef_charId_to_avatarUrl,
    format_war_echoes_date,
    get_equip_rarity_color,
    war_echoes_stage_asset,
    time_to_next_monday_4am,
    war_echoes_rating_asset,
    format_war_echoes_duration,
    war_echoes_potential_asset,
)


async def render_operator_roster(
    *,
    props: OperatorRoster,
    background_image: str | Url | None,
) -> bytes:
    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="operator_roster.html.jinja2",
        templates={
            "props": props,
            "background_image": background_image,
        },
        pages={
            "viewport": {"width": 706, "height": 1},
            "base_url": TEMPLATES_DIR.as_uri(),
        },
        device_scale_factor=1.5,
        screenshot_timeout=config.render_timeout,
        readiness="resources",
        type=config.roster_render_format,
        quality=config.roster_jpeg_quality if config.roster_render_format == "jpeg" else None,
    )


async def render_bound_roles_card(props: BoundRolesCard) -> bytes:
    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="bound_roles.html.jinja2",
        templates={"props": props},
        pages={
            "viewport": {"width": 706, "height": 1},
            "base_url": TEMPLATES_DIR.as_uri(),
        },
        device_scale_factor=1.5,
        screenshot_timeout=config.render_timeout,
        type="png",
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
            "base_url": TEMPLATES_DIR.as_uri(),
        },
        screenshot_timeout=config.render_timeout,
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
            "base_url": TEMPLATES_DIR.as_uri(),
        },
        device_scale_factor=1.5,
        screenshot_timeout=config.render_timeout,
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
            "base_url": TEMPLATES_DIR.as_uri(),
        },
        device_scale_factor=1.5,
        screenshot_timeout=config.render_timeout,
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
            "base_url": TEMPLATES_DIR.as_uri(),
        },
        device_scale_factor=1.5,
        screenshot_timeout=config.render_timeout,
    )


async def render_gacha_history(
    props: GroupedGachaRecord,
    status: Status,
    nickname: str,
    channel_master_id: str,
    begin: int | None = None,
    limit: int | None = None,
) -> bytes:
    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="gacha.html.jinja2",
        templates={
            "record": props,
            "nickname": nickname,
            "channel_master_id": channel_master_id,
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
            "base_url": TEMPLATES_DIR.as_uri(),
        },
        device_scale_factor=1.5,
        screenshot_timeout=config.render_timeout,
    )


EF_GACHA_PAGE_WIDTH = 800
EF_GACHA_PAGE_HEIGHT = 1600


async def render_ef_gacha_history(props: EfGachaView) -> list[bytes]:
    """Measure complete event cards, paginate them, and capture bounded pages."""
    html = await template_to_html(
        template_path=str(TEMPLATES_DIR),
        template_name="ef_gacha.html.jinja2",
        props=props,
        filters={
            "format_timestamp_md": format_timestamp_md,
            "ef_charId_to_avatarUrl": ef_charId_to_avatarUrl,
        },
    )
    async with open_html_page(
        html,
        template_path=TEMPLATES_DIR.as_uri(),
        wait_until="load",
        device_scale_factor=1.5,
        before_load=lambda page: page.set_default_timeout(config.render_timeout),
        viewport={"width": EF_GACHA_PAGE_WIDTH, "height": EF_GACHA_PAGE_HEIGHT},
        base_url=TEMPLATES_DIR.as_uri(),
    ) as page:
        await wait_for_page_resources(page, config.render_timeout)
        page_count = await page.evaluate(
            "options => window.paginateEndfieldGacha(options)",
            {"maxHeight": EF_GACHA_PAGE_HEIGHT, "maxPools": config.ef_gacha_render_max},
        )
        await wait_for_page_resources(page, config.render_timeout)
        pages = page.locator("#ef-pages > .ef-page")
        return [
            await pages.nth(index).screenshot(type="png", timeout=config.render_timeout) for index in range(page_count)
        ]


async def render_ef_war_echoes(props: WarEchoesView) -> bytes:
    return await template_to_pic(
        template_path=str(TEMPLATES_DIR),
        template_name="ef_war_echoes.html.jinja2",
        templates={"view": props},
        filters={
            "war_echoes_asset": war_echoes_asset,
            "war_echoes_rating_asset": war_echoes_rating_asset,
            "war_echoes_stage_asset": war_echoes_stage_asset,
            "war_echoes_potential_asset": war_echoes_potential_asset,
            "get_property_icon": get_property_icon,
            "get_rarity_color": get_rarity_color,
            "format_war_echoes_date": format_war_echoes_date,
            "format_war_echoes_duration": format_war_echoes_duration,
        },
        pages={
            "viewport": {"width": 422, "height": 1},
            "base_url": TEMPLATES_DIR.as_uri(),
        },
        device_scale_factor=2,
        screenshot_timeout=config.render_timeout,
        readiness="resources",
    )


async def render_ef_card(props: EndfieldCard, bg: str | Url, show_all: bool = False, is_simple: bool = False) -> bytes:
    # 预处理角色列表：根据 show_all 决定是否过滤
    if show_all:
        filtered_chars = props.chars
    else:
        # 按 config.charIds 过滤并保持顺序
        char_map = {char.charData.id: char for char in props.chars}
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
    simple_bg = (RES_DIR / "images" / "background" / "endfield" / "simple" / "simple_bg.png").resolve().as_uri()
    simple_bg_top = (RES_DIR / "images" / "background" / "endfield" / "simple" / "simple_bg_top.png").resolve().as_uri()

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
            "base_url": TEMPLATES_DIR.as_uri(),
        },
        screenshot_timeout=config.render_timeout,
    )
