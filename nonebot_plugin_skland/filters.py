import json
from urllib.parse import quote
from datetime import datetime, timedelta

from nonebot import logger

from .config import CACHE_DIR


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


def format_timestamp_str(stamp_str: str) -> str:
    return datetime.fromtimestamp(float(stamp_str)).strftime("%Y-%m-%d %H:%M:%S")


def format_timestamp_md(ms: int) -> str:
    if ms > 1e10:
        return datetime.fromtimestamp(ms / 1000).strftime("%m-%d")
    else:
        return datetime.fromtimestamp(ms).strftime("%m-%d")


def charId_to_avatarUrl(charId: str) -> str:
    avatar_id = next(
        (charId.replace(symbol, "_", 1) for symbol in ["@", "#"] if symbol in charId),
        charId,
    )
    img_path = CACHE_DIR / "avatar" / f"{avatar_id}.png"
    if not img_path.exists():
        img_url = f"https://web.hycdn.cn/arknights/game/assets/char/avatar/{charId}.png"
        logger.debug(f"Avatar not found locally, using URL: {img_url}")
        return img_url
    return img_path.as_uri()


def charId_to_portraitUrl(charId: str) -> str:
    portrait_id = next(
        (charId.replace(symbol, "_", 1) for symbol in ["@", "#"] if symbol in charId),
        charId,
    )
    img_path = CACHE_DIR / "portrait" / f"{portrait_id}.png"
    if not img_path.exists():
        encoded_id = quote(charId, safe="")
        img_url = f"https://web.hycdn.cn/arknights/game/assets/char/portrait/{encoded_id}.png"
        logger.debug(f"Portrait not found locally, using URL: {img_url}")
        return img_url
    return img_path.as_uri()


def loads_json(json_str: str) -> dict:
    return json.loads(json_str)


def format_stamina_time(remaining_seconds: float) -> str:
    """将剩余秒数格式化为 XXh XXmin 格式"""
    if remaining_seconds <= 0:
        return "已满"
    hours = int(remaining_seconds // 3600)
    minutes = int((remaining_seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}min"
    return f"{minutes}min"


def format_date_ymd(timestamp: str | float) -> str:
    """将时间戳格式化为 YYYY-MM-DD 格式（苏醒日）"""
    ts = float(timestamp) if isinstance(timestamp, str) else timestamp
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


# 据点映射表：domainId -> {name, gradient}
DOMAIN_MAP: dict[str, dict[str, str]] = {
    "domain_1": {"name": "四号谷地", "gradient": "green-linear"},
    "domain_2": {"name": "武陵", "gradient": "blue-linear"},
}


def get_domain_info(domain_id: str) -> dict[str, str]:
    """根据 domainId 获取据点信息（名称和渐变样式类）"""
    return DOMAIN_MAP.get(domain_id, {"name": "未知据点", "gradient": "gray-linear"})


# 稀有度到边框颜色映射
RARITY_COLOR_MAP: dict[str, str] = {
    "rarity_6": "#FF7101",  # 6星橙色
    "rarity_5": "#FFCC00",  # 5星金色
    "rarity_4": "#A85FD6",  # 4星紫色
    "rarity_3": "#00B0FF",  # 3星蓝色
}


def get_rarity_color(rarity_key: str) -> str:
    """根据稀有度 key 获取边框颜色"""
    return RARITY_COLOR_MAP.get(rarity_key, "#FFFFFF")


# 装备稀有度到边框颜色映射
EQUIP_RARITY_COLOR_MAP: dict[str, str] = {
    "equip_rarity_6": "#FF7101",
    "equip_rarity_5": "#FFCC00",
    "equip_rarity_4": "#A85FD6",
    "equip_rarity_3": "#00B0FF",
}


def get_equip_rarity_color(rarity_key: str) -> str:
    """根据装备稀有度 key 获取边框颜色"""
    return EQUIP_RARITY_COLOR_MAP.get(rarity_key, "#FFFFFF")


# 职业 key 到图片文件名映射
PROFESSION_MAP: dict[str, str] = {
    "profession_assault": "assault",
    "profession_supporter": "supporter",
    "profession_caster": "caster",
    "profession_vanguard": "vanguard",
    "profession_guard": "guard",
    "profession_defender": "defender",
    "profession_sniper": "sniper",
    "profession_medic": "medic",
}


def get_profession_icon(profession_key: str) -> str:
    """根据职业 key 获取图片文件名"""
    name = PROFESSION_MAP.get(profession_key, "unknown")
    return f"profession/{name}.png"


# 属性 key 到图片文件名映射
PROPERTY_MAP: dict[str, str] = {
    "char_property_fire": "fire",
    "char_property_cryst": "cryst",
    "char_property_natural": "natural",
    "char_property_pulse": "pulse",
    "char_property_physical": "physical",
}


def get_property_icon(property_key: str) -> str:
    """根据属性 key 获取图片文件名"""
    name = PROPERTY_MAP.get(property_key, "unknown")
    return f"property/{name}.png"
