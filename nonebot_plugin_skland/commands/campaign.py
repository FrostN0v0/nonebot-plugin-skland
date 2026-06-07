"""Campaign reward reminder commands"""

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass

from nonebot import logger
from nonebot_plugin_user import UserSession
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_alconna import At, MsgTarget, Target, UniMessage

from ..api import SklandAPI
from ..model import SkUser, CampaignReminder
from ..schemas import CRED, ArkCard
from ..db_handler import (
    get_campaign_reminder,
    upsert_campaign_reminder,
    disable_campaign_reminder,
    get_default_arknights_character_or_none,
)
from ..utils import (
    send_reaction,
    refresh_cred_token_if_needed,
    refresh_access_token_if_needed,
    refresh_cred_token_with_error_return,
    refresh_access_token_with_error_return,
)


@dataclass(frozen=True)
class CampaignReminderPending:
    platform_user_id: str
    nickname: str
    reward_current: int
    reward_total: int


@dataclass(frozen=True)
class CampaignReminderGroupResult:
    target: Target
    pending: list[CampaignReminderPending]


def campaign_target_group_key(notify_target: str) -> str:
    """Normalize notify target JSON so reminders in the same group share one key."""
    return json.dumps(Target.load(json.loads(notify_target)).dump(), sort_keys=True)


def build_merged_campaign_reminder_message(pending: list[CampaignReminderPending]) -> UniMessage:
    if not pending:
        raise ValueError("pending campaign reminders must not be empty")
    if len(pending) == 1:
        item = pending[0]
        return UniMessage(
            At(item.platform_user_id),
            "【剿灭提醒】",
            f"{item.nickname} 的本周剿灭奖励尚未领满：{item.reward_current}/{item.reward_total}，请及时完成剿灭作战。",
        )

    message = UniMessage()
    for item in pending:
        message += At(item.platform_user_id)
    message += "【剿灭提醒】以下角色的本周剿灭奖励尚未领满："
    for item in pending:
        message += f"\n- {item.nickname}：{item.reward_current}/{item.reward_total}"
    message += "\n请及时完成剿灭作战。"
    return message


@refresh_cred_token_with_error_return
@refresh_access_token_with_error_return
async def fetch_ark_card_for_reminder(user: SkUser, uid: str) -> ArkCard | str:
    return await SklandAPI.ark_card(CRED(cred=user.cred, token=user.cred_token), uid)


async def _evaluate_campaign_reminder(
    session: async_scoped_session,
    reminder: CampaignReminder,
) -> CampaignReminderPending | None:
    user = await session.get(SkUser, reminder.user_id)
    if not user:
        return None

    character = await get_default_arknights_character_or_none(user, session)
    if not character:
        return None

    character_nickname = character.nickname
    character_uid = str(character.uid)
    card = await fetch_ark_card_for_reminder(user, character_uid)
    if isinstance(card, str):
        logger.warning(f"Campaign reminder failed for user {user.id}: {card}")
        return None
    if card.campaign.is_reward_complete:
        return None

    reward = card.campaign.reward
    return CampaignReminderPending(
        platform_user_id=reminder.platform_user_id,
        nickname=character_nickname,
        reward_current=reward.current,
        reward_total=reward.total,
    )


async def gather_campaign_reminder_groups(
    session: async_scoped_session,
    reminders: list[CampaignReminder],
) -> list[CampaignReminderGroupResult]:
    grouped: dict[str, list[CampaignReminder]] = defaultdict(list)
    for reminder in reminders:
        grouped[campaign_target_group_key(reminder.notify_target)].append(reminder)

    results: list[CampaignReminderGroupResult] = []
    for group_reminders in grouped.values():
        target = Target.load(json.loads(group_reminders[0].notify_target))
        pending_results = await asyncio.gather(
            *(_evaluate_campaign_reminder(session, reminder) for reminder in group_reminders)
        )
        pending = [item for item in pending_results if item is not None]
        if pending:
            results.append(CampaignReminderGroupResult(target=target, pending=pending))
    return results


async def _require_bound_user(user_session: UserSession, session: async_scoped_session) -> SkUser:
    user = await session.get(SkUser, user_session.user_id)
    if not user:
        send_reaction(user_session, "unmatch")
        await UniMessage("未绑定 skland 账号").finish(at_sender=True)
    return user


@refresh_cred_token_if_needed
@refresh_access_token_if_needed
async def _fetch_default_ark_card(user: SkUser, uid: str) -> ArkCard:
    return await SklandAPI.ark_card(CRED(cred=user.cred, token=user.cred_token), uid)


async def campaign_on_handler(
    user_session: UserSession,
    session: async_scoped_session,
    msg_target: MsgTarget,
):
    """Enable campaign reward reminder in current group chat"""

    if msg_target.private:
        send_reaction(user_session, "unmatch")
        await UniMessage("剿灭提醒需在群聊中开启，请在群聊内发送该指令").finish(at_sender=True)

    user = await _require_bound_user(user_session, session)
    character = await get_default_arknights_character_or_none(user, session)
    if not character:
        send_reaction(user_session, "unmatch")
        await UniMessage("未绑定明日方舟默认角色").finish(at_sender=True)

    character_nickname = character.nickname
    notify_target = json.dumps(msg_target.dump())
    await upsert_campaign_reminder(
        session,
        user.id,
        notify_target,
        user_session.platform_user.id,
    )
    await session.commit()
    send_reaction(user_session, "done")
    await UniMessage(
        "已在本群开启剿灭提醒，将在每周日 12:00 和 18:00（上海时间）"
        f"检测默认角色 {character_nickname} 的剿灭奖励领取情况。"
    ).finish(at_sender=True)


async def campaign_off_handler(user_session: UserSession, session: async_scoped_session):
    """Disable campaign reward reminder"""

    await _require_bound_user(user_session, session)
    disabled = await disable_campaign_reminder(user_session.user_id, session)
    await session.commit()
    send_reaction(user_session, "done" if disabled else "unmatch")
    if disabled:
        await UniMessage("已关闭剿灭提醒").finish(at_sender=True)
    else:
        await UniMessage("尚未开启剿灭提醒").finish(at_sender=True)


async def campaign_status_handler(user_session: UserSession, session: async_scoped_session):
    """Show campaign reminder status and current reward progress"""

    user = await _require_bound_user(user_session, session)
    reminder = await get_campaign_reminder(user.id, session)
    character = await get_default_arknights_character_or_none(user, session)
    if not character:
        send_reaction(user_session, "unmatch")
        await UniMessage("未绑定明日方舟默认角色").finish(at_sender=True)

    character_nickname = character.nickname
    character_uid = str(character.uid)
    status_lines = [
        f"剿灭提醒：{'已开启' if reminder and reminder.enabled else '未开启'}",
    ]
    if reminder and reminder.enabled:
        target = Target.load(json.loads(reminder.notify_target))
        status_lines.append(f"提醒群聊：{target.id}")

    send_reaction(user_session, "processing")
    card = await _fetch_default_ark_card(user, character_uid)
    if not card:
        return

    reward = card.campaign.reward
    status_lines.append(
        f"默认角色 {character_nickname} 剿灭奖励：{reward.current}/{reward.total}"
        f"（{'已完成' if card.campaign.is_reward_complete else '未完成'}）"
    )
    send_reaction(user_session, "done")
    await UniMessage("\n".join(status_lines)).finish(at_sender=True)
    await session.commit()
