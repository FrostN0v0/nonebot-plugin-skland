from sqlalchemy import select
from nonebot_plugin_orm import async_scoped_session

from .model import User, Character


async def get_arknights_characters(user: User, session: async_scoped_session):
    characters = (
        (
            await session.execute(
                select(Character).where(Character.id == user.id).where(Character.app_code == "arknights")
            )
        )
        .scalars()
        .all()
    )
    return characters
