from datetime import datetime, timedelta


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
