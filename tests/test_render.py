from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_all_template_renderers_use_configured_timeout(app, mocker, monkeypatch):
    from nonebot_plugin_skland import render
    from nonebot_plugin_skland.config import config

    monkeypatch.setattr(config, "render_timeout", 321_000)
    template_renderer = mocker.patch.object(
        render,
        "template_to_pic",
        new=mocker.AsyncMock(return_value=b"image"),
    )

    ark_card = SimpleNamespace(
        status=object(),
        chars=[],
        skins=[],
        building=object(),
        medal=SimpleNamespace(total=0),
        assistChars=[],
        recruit_finished=0,
        recruit=[],
        recruit_complete_time=None,
        campaign=object(),
        routine=object(),
        tower=object(),
        trainee_char=None,
    )
    rogue_history = SimpleNamespace(favourRecords=[], records=[])
    rogue_data = SimpleNamespace(
        topic_img="",
        topic="",
        career=object(),
        gameUserInfo=object(),
        history=rogue_history,
    )
    ef_gacha = SimpleNamespace(joint_pools=[])
    ef_card = SimpleNamespace(
        chars=[],
        config=SimpleNamespace(charIds=[]),
        spaceShip=SimpleNamespace(rooms=[]),
        domain=[],
        currentTs=None,
        dungeon=SimpleNamespace(maxTs=None, curStamina=None, maxStamina=None),
        base=object(),
        bpSystem=object(),
        dailyMission=object(),
        weeklyMission=object(),
        achieve=object(),
    )

    await render.render_operator_roster(props=object(), background_image=None)
    await render.render_ark_card(ark_card, "background.jpg")
    await render.render_rogue_card(rogue_data, "background.jpg")
    await render.render_rogue_info(rogue_data, "background.jpg", 1, False)
    await render.render_clue_board(object())
    await render.render_gacha_history(object(), object(), object())
    await render.render_ef_gacha_history(ef_gacha, SimpleNamespace(avatarUrl=""), object())
    await render.render_ef_card(ef_card, "background.jpg")

    assert template_renderer.await_count == 8
    assert {call.kwargs["template_name"] for call in template_renderer.await_args_list} == {
        "operator_roster.html.jinja2",
        "ark_card.html.jinja2",
        "rogue.html.jinja2",
        "rogue_info.html.jinja2",
        "clue.html.jinja2",
        "gacha.html.jinja2",
        "ef_gacha.html.jinja2",
        "endfield_card.html.jinja2",
    }
    assert all(call.kwargs["screenshot_timeout"] == 321_000 for call in template_renderer.await_args_list)
