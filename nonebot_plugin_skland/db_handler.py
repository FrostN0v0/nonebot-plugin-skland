from sqlalchemy import delete, select
from nonebot_plugin_orm import async_scoped_session

from .model import SkUser, Character, GachaRecord, CampaignReminder


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


async def get_default_arknights_character_or_none(user: SkUser, session: async_scoped_session) -> Character | None:
    return (
        await session.execute(
            select(Character).where(
                Character.id == user.id,
                Character.isdefault,
                Character.app_code == "arknights",
            )
        )
    ).scalar_one_or_none()


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


async def get_endfield_character_by_role_id(user: SkUser, role_id: str, session: async_scoped_session) -> Character:
    character = (
        await session.execute(
            select(Character).where(
                Character.id == user.id,
                Character.role_id == role_id,
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


async def select_all_ef_gacha_records(user: SkUser, char_uid: str, session: async_scoped_session) -> list[GachaRecord]:
    """查询指定用户和角色的所有终末地抽卡记录"""
    records = (
        (
            await session.execute(
                select(GachaRecord).where(
                    GachaRecord.uid == user.id,
                    GachaRecord.char_uid == char_uid,
                    GachaRecord.app_code == "endfield",
                )
            )
        )
        .scalars()
        .all()
    )
    return list(records)


async def delete_user_all_gacha_records(user: SkUser, session: async_scoped_session):
    """删除用户的所有抽卡记录"""
    await session.execute(delete(GachaRecord).where(GachaRecord.uid == user.id))


async def delete_user(user: SkUser, session: async_scoped_session):
    """删除用户"""
    await session.delete(user)


async def get_campaign_reminder(user_id: int, session: async_scoped_session) -> CampaignReminder | None:
    return await session.get(CampaignReminder, user_id)


async def select_enabled_campaign_reminders(session: async_scoped_session) -> list[CampaignReminder]:
    reminders = (await session.scalars(select(CampaignReminder).where(CampaignReminder.enabled.is_(True)))).all()
    return list(reminders)


async def upsert_campaign_reminder(
    session: async_scoped_session,
    user_id: int,
    notify_target: str,
    platform_user_id: str,
) -> CampaignReminder:
    reminder = await session.get(CampaignReminder, user_id)
    if reminder:
        reminder.enabled = True
        reminder.notify_target = notify_target
        reminder.platform_user_id = platform_user_id
        return reminder

    reminder = CampaignReminder(
        user_id=user_id,
        enabled=True,
        notify_target=notify_target,
        platform_user_id=platform_user_id,
    )
    session.add(reminder)
    return reminder


async def disable_campaign_reminder(user_id: int, session: async_scoped_session) -> bool:
    reminder = await session.get(CampaignReminder, user_id)
    if not reminder or not reminder.enabled:
        return False
    reminder.enabled = False
    return True
