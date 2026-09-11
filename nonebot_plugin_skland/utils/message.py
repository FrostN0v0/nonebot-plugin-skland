"""Small interaction helpers shared by commands."""

import contextlib
from pathlib import Path
from typing import Literal

from nonebot import get_driver
from nonebot_plugin_user import UserSession
from nonebot_plugin_alconna import Text, Image, Segment, UniMessage, message_reaction

from ..exception import SklandException
from .background import BackgroundImage


def build_background_argot_segment(background: BackgroundImage) -> Image | list[Segment]:
    if isinstance(background, Path):
        return Image(path=background)
    url = str(background)
    return [Text(url), Image(url=url)]


def send_reaction(
    user_session: UserSession, emoji: Literal["fail", "done", "processing", "received", "unmatch"]
) -> None:
    emoji_map = {
        "fail": ["10060", "❌"],
        "done": ["144", "🎉"],
        "processing": ["66", "❤"],
        "received": ["124", "👌"],
        "unmatch": ["326", "🤖"],
    }

    async def send() -> None:
        with contextlib.suppress(Exception):
            await message_reaction(emoji_map[emoji][0] if user_session.platform == "QQClient" else emoji_map[emoji][1])

    get_driver().task_group.start_soon(send)


async def send_request_error(error: SklandException) -> None:
    """Present API failures only at the interactive command boundary."""
    await UniMessage(f"接口请求失败,{error.args[0]}").send(at_sender=True)
