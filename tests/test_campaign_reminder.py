def test_campaign_is_reward_complete(app):
    from nonebot_plugin_skland.schemas.arknights.models.base import BaseCount
    from nonebot_plugin_skland.schemas.arknights.models.campaign import Campaign

    complete = Campaign(records=[], reward=BaseCount(current=1, total=1))
    incomplete = Campaign(records=[], reward=BaseCount(current=0, total=1))
    zero_total = Campaign(records=[], reward=BaseCount(current=0, total=0))

    assert complete.is_reward_complete is True
    assert incomplete.is_reward_complete is False
    assert zero_total.is_reward_complete is False


def test_build_merged_campaign_reminder_message_single(app):
    from nonebot_plugin_alconna import At
    from nonebot_plugin_skland.commands.campaign import (
        CampaignReminderPending,
        build_merged_campaign_reminder_message,
    )

    message = build_merged_campaign_reminder_message(
        [CampaignReminderPending("10001", "Doctor", 0, 1)]
    )

    assert len(message) == 3
    assert isinstance(message[0], At)
    assert message[0].target == "10001"


def test_build_merged_campaign_reminder_message_multiple(app):
    from nonebot_plugin_skland.commands.campaign import (
        CampaignReminderPending,
        build_merged_campaign_reminder_message,
    )

    single = build_merged_campaign_reminder_message(
        [CampaignReminderPending("10001", "DoctorA", 0, 1)]
    )
    merged = build_merged_campaign_reminder_message(
        [
            CampaignReminderPending("10001", "DoctorA", 0, 1),
            CampaignReminderPending("10002", "DoctorB", 0, 1),
        ]
    )

    assert len(merged) > len(single)


def test_campaign_target_group_key(app):
    import json

    from nonebot_plugin_skland.commands.campaign import campaign_target_group_key

    target_a = {
        "id": "123456",
        "parent_id": "",
        "channel": False,
        "private": False,
        "self_id": "2333",
        "extra": {},
        "scope": "QQClient",
    }
    target_b = {
        "scope": "QQClient",
        "id": "123456",
        "private": False,
        "self_id": "2333",
        "channel": False,
        "parent_id": "",
        "extra": {},
    }

    assert campaign_target_group_key(json.dumps(target_a)) == campaign_target_group_key(json.dumps(target_b))


async def test_refresh_access_token_with_error_return_no_access_token(app, mocker):
    from nonebot_plugin_skland.utils import refresh_access_token_with_error_return
    from nonebot_plugin_skland.model import SkUser
    from nonebot_plugin_skland.exception import LoginException

    @refresh_access_token_with_error_return
    async def _fetch(_user: SkUser) -> str:
        raise LoginException("cred expired")

    user = SkUser(id=1, cred="cred", cred_token="token", access_token="")
    send = mocker.patch("nonebot_plugin_skland.utils.UniMessage.send")

    result = await _fetch(user)

    assert result == "cred失效，用户没有绑定token，无法自动刷新cred"
    send.assert_not_called()
