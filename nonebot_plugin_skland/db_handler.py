from sqlalchemy import delete, select
from nonebot_plugin_orm import async_scoped_session

from .model import User, Character


async def get_default_arknights_character(user: User, session: async_scoped_session) -> Character:
    character = (
        await session.execute(
            select(Character).where(
                Character.id == user.id,
                Character.isdefault,
                Character.app_code == "arknights",
            )
        )
    ).scalar_one()
    return character


async def get_arknights_character_by_uid(user: User, uid: str, session: async_scoped_session) -> Character:
    character = (
        await session.execute(
            select(Character).where(
                Character.id == user.id,
                Character.uid == int(uid),
                Character.app_code == "arknights",
            )
        )
    ).scalar_one()
    return character


async def delete_characters(user: User, session: async_scoped_session):
    await session.execute(delete(Character).where(Character.id == user.id))
