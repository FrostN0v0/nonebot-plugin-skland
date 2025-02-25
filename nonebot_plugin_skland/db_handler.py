from sqlalchemy import delete, select
from nonebot_plugin_orm import async_scoped_session

from .model import User, Character


async def get_arknights_characters(user: User, session: async_scoped_session) -> list[Character]:
    characters = (
        (
            await session.execute(
                select(Character).where(Character.id == user.id).where(Character.app_code == "arknights")
            )
        )
        .scalars()
        .all()
    )
    return list(characters)


async def get_arknights_character_by_uid(user: User, uid: str, session: async_scoped_session) -> Character:
    characters = (
        await session.execute(
            select(Character).where(
                Character.id == user.id,
                Character.uid == int(uid),
                Character.app_code == "arknights",
            )
        )
    ).scalar_one()
    return characters


async def delete_characters(user: User, session: async_scoped_session):
    await session.execute(delete(Character).where(Character.id == user.id))
