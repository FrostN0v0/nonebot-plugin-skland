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
