"""Campaign reward reminder commands"""

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
    select_enabled_campaign_reminders,
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
        return (
            UniMessage()
            + At("user", item.platform_user_id)
            + "【剿灭提醒】"
            + f"{item.nickname} 的本周剿灭奖励尚未领满：{item.reward_current}/{item.reward_total}，请及时完成剿灭作战。"
        )

    message = UniMessage()
    for item in pending:
        message += At("user", item.platform_user_id)
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
        pending: list[CampaignReminderPending] = []
        for reminder in group_reminders:
            try:
                item = await _evaluate_campaign_reminder(session, reminder)
            except Exception as e:
                logger.warning(f"Campaign reminder evaluation failed for user {reminder.user_id}: {e}")
                continue
            if item is not None:
                pending.append(item)
        if pending:
            results.append(CampaignReminderGroupResult(target=target, pending=pending))
    return results


async def dispatch_campaign_reminders(session: async_scoped_session) -> tuple[int, int, int]:
    """Evaluate enabled reminders and send group notifications.

    Returns:
        sent_groups, pending_groups, enabled_reminders
    """
    from nonebot import get_bots

    bots = get_bots()
    if not bots:
        raise RuntimeError("no connected bot")

    reminders = await select_enabled_campaign_reminders(session)
    enabled_count = len(reminders)
    if not reminders:
        return 0, 0, 0

    groups = await gather_campaign_reminder_groups(session, reminders)
    sent = 0
    for group_result in groups:
        target = group_result.target
        bot = bots.get(target.self_id) if target.self_id else None
        if bot is None:
            bot = next(iter(bots.values()))
            logger.warning(
                f"Campaign reminder: bot {target.self_id!r} not connected, "
                f"fallback to {bot.self_id!r} for group {target.id}"
            )

        message = build_merged_campaign_reminder_message(group_result.pending)
        try:
            await message.send(target=target, bot=bot)
            sent += 1
        except Exception as e:
            user_ids = ", ".join(item.platform_user_id for item in group_result.pending)
            logger.warning(f"Campaign reminder send failed for group {target.id} users [{user_ids}]: {e}")

    return sent, len(groups), enabled_count


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


async def campaign_test_handler(
    user_session: UserSession,
    session: async_scoped_session,
    msg_target: MsgTarget,
    bot,
    *,
    run_all: bool,
    do_send: bool,
    is_superuser: bool,
):
    """Manually test campaign reminder without waiting for Sunday cron."""

    if run_all:
        if not is_superuser:
            send_reaction(user_session, "unmatch")
            await UniMessage("全量测试仅超级用户可用").finish(at_sender=True)

        send_reaction(user_session, "processing")
        try:
            sent, pending_groups, enabled = await dispatch_campaign_reminders(session)
        except RuntimeError:
            send_reaction(user_session, "error")
            await UniMessage("无已连接的 bot，无法发送测试提醒").finish(at_sender=True)
            return
        await session.commit()
        send_reaction(user_session, "done")
        await UniMessage(
            "剿灭提醒全量测试完成\n"
            f"- 已开启提醒：{enabled} 人\n"
            f"- 待通知群聊：{pending_groups} 个\n"
            f"- 已发送：{sent} 条"
        ).finish(at_sender=True)
        return

    user = await _require_bound_user(user_session, session)
    character = await get_default_arknights_character_or_none(user, session)
    if not character:
        send_reaction(user_session, "unmatch")
        await UniMessage("未绑定明日方舟默认角色").finish(at_sender=True)

    reminder = await get_campaign_reminder(user.id, session)
    lines = [
        "【剿灭提醒测试】",
        f"提醒状态：{'已开启' if reminder and reminder.enabled else '未开启'}",
    ]
    if reminder and reminder.enabled:
        target = Target.load(json.loads(reminder.notify_target))
        lines.append(f"绑定群聊：{target.id}")
        if not msg_target.private and msg_target.id != target.id:
            lines.append(f"当前群聊：{msg_target.id}（与绑定群不一致，--send 将发到当前群）")

    send_reaction(user_session, "processing")
    card = await fetch_ark_card_for_reminder(user, str(character.uid))
    if isinstance(card, str):
        send_reaction(user_session, "error")
        await UniMessage(f"接口请求失败：{card}").finish(at_sender=True)
        return

    reward = card.campaign.reward
    lines.append(
        f"默认角色 {character.nickname}：{reward.current}/{reward.total}"
        f"（{'已完成' if card.campaign.is_reward_complete else '未完成'}）"
    )

    pending: CampaignReminderPending | None = None
    if reminder and reminder.enabled:
        pending = await _evaluate_campaign_reminder(session, reminder)

    if pending:
        lines.append("结论：周日定时任务会 @ 你发送提醒")
        if do_send:
            if msg_target.private:
                send_reaction(user_session, "unmatch")
                await UniMessage("发送测试提醒需在群聊中使用 --send").finish(at_sender=True)
                return
            message = build_merged_campaign_reminder_message([pending])
            await message.send(target=msg_target, bot=bot)
            lines.append("已在当前群发送测试提醒")
    elif card.campaign.is_reward_complete:
        lines.append("结论：奖励已满，周日定时任务不会提醒")
    elif not reminder or not reminder.enabled:
        lines.append("结论：未开启提醒，请先使用 skland campaign on")
    else:
        lines.append("结论：不满足提醒条件（接口异常或角色缺失）")

    await session.commit()
    send_reaction(user_session, "done")
    await UniMessage("\n".join(lines)).finish(at_sender=True)
