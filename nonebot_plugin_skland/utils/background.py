"""Configured local and remote background selection."""

from typing import Literal

import httpx
from pydantic import AnyUrl as Url

from ..config import RES_DIR, CustomSource, config


async def get_lolicon_image(tag: str = "arknights") -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.lolicon.app/setu/v2?tag={tag}")
    return response.json()["data"][0]["urls"]["original"]


async def get_background_image(game_type: Literal["ark", "endfield"] = "ark") -> str | Url:
    if game_type == "endfield":
        default_background = RES_DIR / "images" / "background" / "endfield" / "default_bg.jpg"
        random_dir = RES_DIR / "images" / "background" / "endfield"
        lolicon_tag = "endfield"
    else:
        default_background = RES_DIR / "images" / "background" / "bg.jpg"
        random_dir = RES_DIR / "images" / "background"
        lolicon_tag = "arknights"

    match config.background_source:
        case "default":
            background_image = default_background.resolve().as_uri()
        case "Lolicon":
            background_image = await get_lolicon_image(lolicon_tag)
        case "random":
            background_image = CustomSource(uri=random_dir).to_uri()
        case CustomSource() as cs:
            background_image = cs.to_uri()
        case _:
            background_image = default_background.resolve().as_uri()
    return background_image


async def get_rogue_background_image(rogue_id: str) -> str | Url:
    default_background = RES_DIR / "images" / "background" / "rogue" / "kv_epoque14.png"
    default_rogue_background_map = {
        "rogue_1": RES_DIR / "images" / "background" / "rogue" / "pic_rogue_1_KV1.png",
        "rogue_2": RES_DIR / "images" / "background" / "rogue" / "pic_rogue_2_50.png",
        "rogue_3": RES_DIR / "images" / "background" / "rogue" / "pic_rogue_3_KV2.png",
        "rogue_4": RES_DIR / "images" / "background" / "rogue" / "pic_rogue_4_47.png",
        "rogue_5": RES_DIR / "images" / "background" / "rogue" / "pic_rogue_5_KV1.png",
        "rogue_6": RES_DIR / "images" / "background" / "rogue" / "pic_rogue_6_kv1.png",
    }
    match config.rogue_background_source:
        case "default":
            background_image = default_background.resolve().as_uri()
        case "rogue":
            background_image = default_rogue_background_map.get(rogue_id, default_background).resolve().as_uri()
        case "Lolicon":
            background_image = await get_lolicon_image()
        case CustomSource() as cs:
            background_image = cs.to_uri()
    return background_image
