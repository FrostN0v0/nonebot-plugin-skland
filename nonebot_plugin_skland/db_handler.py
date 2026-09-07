from sqlalchemy import select
from sqlalchemy.orm import joinedload
from nonebot_plugin_orm import async_scoped_session

from .model import SkUser, Character, GachaRecord, CharacterDefault


async def get_accounts(owner_id: int, session: async_scoped_session) -> list[SkUser]:
    accounts = await session.scalars(select(SkUser).where(SkUser.owner_id == owner_id).order_by(SkUser.id))
    return list(accounts)


async def get_account(
    owner_id: int,
    skland_user_id: str,
    session: async_scoped_session,
) -> SkUser | None:
    return await session.scalar(
        select(SkUser).where(
            SkUser.owner_id == owner_id,
            SkUser.skland_user_id == skland_user_id,
        )
    )


async def select_all_accounts(session: async_scoped_session) -> list[SkUser]:
    accounts = await session.scalars(select(SkUser).order_by(SkUser.owner_id, SkUser.id))
    return list(accounts)


async def get_account_characters(account_id: int, session: async_scoped_session) -> list[Character]:
    characters = await session.scalars(
        select(Character)
        .where(Character.account_id == account_id)
        .order_by(Character.app_code, Character.channel_master_id, Character.role_id)
    )
    return list(characters)


async def get_user_characters(
    owner_id: int,
    app_code: str | None,
    session: async_scoped_session,
) -> list[Character]:
    statement = (
        select(Character)
        .join(Character.account)
        .where(SkUser.owner_id == owner_id)
        .options(joinedload(Character.account))
        .order_by(SkUser.id, Character.channel_master_id, Character.role_id)
    )
    if app_code is not None:
        statement = statement.where(Character.app_code == app_code)
    characters = await session.scalars(statement)
    return list(characters)


async def get_default_character(
    owner_id: int,
    app_code: str,
    session: async_scoped_session,
) -> Character | None:
    return await session.scalar(
        select(Character)
        .join(CharacterDefault, CharacterDefault.character_id == Character.id)
        .join(Character.account)
        .where(
            CharacterDefault.owner_id == owner_id,
            CharacterDefault.app_code == app_code,
            Character.app_code == app_code,
            SkUser.owner_id == owner_id,
        )
        .options(joinedload(Character.account))
    )


async def get_character_by_index(
    owner_id: int,
    app_code: str,
    index: int,
    session: async_scoped_session,
) -> Character | None:
    if index < 1:
        return None
    characters = await get_user_characters(owner_id, app_code, session)
    return characters[index - 1] if index <= len(characters) else None


async def set_default_character(
    owner_id: int,
    app_code: str,
    character_id: int,
    session: async_scoped_session,
) -> Character:
    character = await session.scalar(
        select(Character)
        .join(Character.account)
        .where(
            Character.id == character_id,
            Character.app_code == app_code,
            SkUser.owner_id == owner_id,
        )
        .options(joinedload(Character.account))
    )
    if character is None:
        raise ValueError("character does not belong to the requested owner and game")

    default = await session.get(CharacterDefault, (owner_id, app_code))
    if default is None:
        session.add(
            CharacterDefault(
                owner_id=owner_id,
                app_code=app_code,
                character_id=character.id,
            )
        )
    else:
        default.character_id = character.id
    return character


async def get_character_gacha_records(
    character_id: int,
    session: async_scoped_session,
) -> list[GachaRecord]:
    records = await session.scalars(
        select(GachaRecord).where(GachaRecord.character_id == character_id).order_by(GachaRecord.id)
    )
    return list(records)
