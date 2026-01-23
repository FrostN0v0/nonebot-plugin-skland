from sqlalchemy import delete, select
from nonebot_plugin_orm import async_scoped_session

from .model import SkUser, Character, GachaRecord


async def get_arknights_characters(user: SkUser, session: async_scoped_session) -> list[Character]:
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


async def get_default_arknights_character(user: SkUser, session: async_scoped_session) -> Character:
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


async def get_arknights_character_by_uid(user: SkUser, uid: str, session: async_scoped_session) -> Character:
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


async def delete_characters(user: SkUser, session: async_scoped_session):
    await session.execute(delete(Character).where(Character.id == user.id))


async def select_all_users(session: async_scoped_session) -> list[SkUser]:
    users = (await session.execute(select(SkUser))).scalars().all()
    return list(users)


async def select_user_characters(user: SkUser, session: async_scoped_session) -> list[Character]:
    return list((await session.scalars(select(Character).where(Character.id == user.id))).all())


async def select_all_gacha_records(user: SkUser, char_uid: str, session: async_scoped_session) -> list[GachaRecord]:
    records = (
        (await session.execute(select(GachaRecord).where(GachaRecord.uid == user.id, GachaRecord.char_uid == char_uid)))
        .scalars()
        .all()
    )
    return list(records)


async def delete_character_gacha_records(character: Character, session: async_scoped_session):
    await session.execute(
        delete(GachaRecord).where(GachaRecord.char_pk_id == character.id, GachaRecord.char_uid == character.uid)
    )


async def get_default_endfield_character(user: SkUser, session: async_scoped_session) -> Character:
    character = (
        await session.execute(
            select(Character).where(
                Character.id == user.id,
                Character.isdefault,
                Character.app_code == "endfield",
            )
        )
    ).scalar_one()
    return character


async def get_endfield_character_by_uid(user: SkUser, uid: str, session: async_scoped_session) -> Character:
    character = (
        await session.execute(
            select(Character).where(
                Character.id == user.id,
                Character.uid == int(uid),
                Character.app_code == "endfield",
            )
        )
    ).scalar_one()
    return character


async def get_endfield_characters(user: SkUser, session: async_scoped_session) -> list[Character]:
    characters = (
        (
            await session.execute(
                select(Character).where(Character.id == user.id).where(Character.app_code == "endfield")
            )
        )
        .scalars()
        .all()
    )
    return list(characters)
