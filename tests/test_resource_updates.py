import asyncio
import importlib.util
from types import SimpleNamespace
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def resource_loaders(app, mocker):
    from nonebot_plugin_skland.services import resources

    client = mocker.MagicMock()
    client.__aenter__.return_value = client
    mocker.patch.object(resources, "GitHubDataClient", return_value=client)
    ark = SimpleNamespace(version="new-version", load=mocker.AsyncMock(return_value=False))
    ef = SimpleNamespace(pool_table={"pool": {}}, load=mocker.AsyncMock(return_value=False))
    mocker.patch.object(resources, "gacha_table_data", ark)
    mocker.patch.object(resources, "ef_gacha_pool_data", ef)
    return ark, ef


@pytest.mark.parametrize("owner", ["manual", "timer"])
@pytest.mark.asyncio
async def test_manual_and_timer_updates_do_not_overlap(app, resource_loaders, mocker, monkeypatch, owner):
    from nonebot_plugin_skland import tasks
    from nonebot_plugin_skland.commands import sync
    from nonebot_plugin_skland.services import resources
    from nonebot_plugin_skland.matcher import skland_command
    from nonebot_plugin_skland.exception import ResourceUpdateInProgress

    monkeypatch.setattr(tasks.config, "auto_update_resources", True)
    mocker.patch.object(sync, "send_reaction")
    sent = []

    async def send(message, *args, **kwargs):
        sent.append(str(message))

    mocker.patch.object(sync.UniMessage, "send", new=send)
    image_download = mocker.patch.object(sync, "download_img_resource", new=mocker.AsyncMock())
    entered = asyncio.Event()
    release = asyncio.Event()
    writes = []

    async def load_ark(**kwargs):
        writes.append("ark")
        entered.set()
        await release.wait()
        return False

    async def load_ef(**kwargs):
        writes.append("ef")
        return False

    ark, ef = resource_loaders
    ark.load.side_effect = load_ark
    ef.load.side_effect = load_ef
    command = skland_command.parse("/skland sync --data")
    assert command.matched
    user = SimpleNamespace(platform="Console")

    async def manual_update():
        await sync.sync_handler(user, command, is_superuser=True)

    running = asyncio.create_task(manual_update() if owner == "manual" else tasks.run_daily_resource_update())
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        with pytest.raises(ResourceUpdateInProgress):
            await resources.update_data_resources()
        await manual_update()
        assert len(sent) == 1
        assert "正在更新" in sent[0]
        await tasks.run_daily_resource_update()
        assert len(sent) == 1  # A skipped scheduled update does not send a bot message.
        assert writes == ["ark"]
    finally:
        release.set()
        await asyncio.wait_for(running, timeout=5)

    assert writes == ["ark", "ef"]
    await resources.update_data_resources()
    assert writes == ["ark", "ef", "ark", "ef"]
    image_download.assert_not_awaited()


@pytest.mark.parametrize("failed_game", ["ark", "ef"])
@pytest.mark.asyncio
async def test_game_failure_does_not_block_other_game(app, resource_loaders, failed_game):
    from nonebot_plugin_skland.services import resources
    from nonebot_plugin_skland.exception import RequestException

    ark, ef = resource_loaders
    completed = []

    async def load_ark(**kwargs):
        if failed_game == "ark":
            raise RequestException("上游不可用")
        completed.append("ark")
        return True

    async def load_ef(**kwargs):
        if failed_game == "ef":
            raise RequestException("上游不可用")
        completed.append("ef")
        return True

    ark.load.side_effect = load_ark
    ef.load.side_effect = load_ef
    result = await resources.update_data_resources()

    assert result.failed
    assert completed == (["ef"] if failed_game == "ark" else ["ark"])
    failure = result.messages[0 if failed_game == "ark" else 1]
    success = result.messages[1 if failed_game == "ark" else 0]
    assert failure.startswith("❌ ")
    assert "上游不可用" in failure
    assert "已是最新" not in failure
    assert success.startswith("✅ ")


@pytest.mark.asyncio
async def test_forced_unchanged_data_is_not_reported_as_updated(app, resource_loaders):
    from nonebot_plugin_skland.services import resources

    result = await resources.update_data_resources(force=True)

    assert not result.failed
    assert all("已是最新" in message for message in result.messages)
    assert all("更新成功" not in message for message in result.messages)


@pytest.mark.parametrize("ark_changed", [True, False])
@pytest.mark.asyncio
async def test_manual_reply_retains_status_icons_and_endfield_pool_count(app, resource_loaders, mocker, ark_changed):
    from nonebot_plugin_skland.commands import sync
    from nonebot_plugin_skland.matcher import skland_command

    ark, ef = resource_loaders
    ark.load.return_value = ark_changed
    ef.load.return_value = not ark_changed
    ef.pool_table = {"first": {}, "second": {}}
    sent = []

    async def send(message, *args, **kwargs):
        sent.append(str(message))

    mocker.patch.object(sync.UniMessage, "send", new=send)
    mocker.patch.object(sync, "send_reaction")
    command = skland_command.parse("/skland sync --data")
    await sync.sync_handler(SimpleNamespace(platform="Console"), command, is_superuser=True)

    assert len(sent) == 1
    ark_message, ef_message = sent[0].splitlines()
    assert ark_message.startswith("✅ " if ark_changed else "📦 ")
    assert ef_message.startswith("📦 " if ark_changed else "✅ ")
    assert "共 2 个卡池" in ef_message


@pytest.mark.asyncio
async def test_cancelled_update_releases_scope(app, resource_loaders):
    from nonebot_plugin_skland.services import resources

    entered = asyncio.Event()
    blocked = asyncio.Event()

    async def load_ark(**kwargs):
        entered.set()
        await blocked.wait()
        return False

    ark, _ = resource_loaders
    ark.load.side_effect = load_ark
    running = asyncio.create_task(resources.update_data_resources())
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
    finally:
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running

    ark.load.side_effect = None
    result = await resources.update_data_resources()
    assert not result.failed
    assert all("已是最新" in message for message in result.messages)


@pytest.mark.asyncio
async def test_disabled_daily_update_does_not_call_update(app, mocker, monkeypatch):
    from nonebot_plugin_skland import tasks

    monkeypatch.setattr(tasks.config, "auto_update_resources", False)
    update = mocker.patch.object(tasks, "update_data_resources", new=mocker.AsyncMock())

    await tasks.run_daily_resource_update()

    update.assert_not_awaited()


@pytest.mark.parametrize("timezone", ["Asia/Shanghai", "Europe/Berlin"])
def test_daily_update_trigger_uses_configured_timezone(app, monkeypatch, timezone):
    import nonebot_plugin_apscheduler
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from nonebot_plugin_skland import tasks

    scheduler = AsyncIOScheduler(timezone=timezone)
    monkeypatch.setattr(nonebot_plugin_apscheduler, "scheduler", scheduler)
    # Load an isolated module so job registration is exercised without modifying live jobs.
    spec = importlib.util.spec_from_file_location("nonebot_plugin_skland._resource_tasks_test", tasks.__file__)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    job = scheduler.get_job("daily_resource_update")
    assert job is not None

    before = datetime(2026, 9, 9, 8, 59, tzinfo=scheduler.timezone)
    expected = datetime(2026, 9, 9, 9, 0, tzinfo=scheduler.timezone)
    first_fire = job.trigger.get_next_fire_time(None, before)
    assert first_fire == expected
    assert str(job.trigger.timezone) == timezone
    assert job.trigger.get_next_fire_time(first_fire, first_fire) == expected + timedelta(days=1)


@pytest.mark.asyncio
async def test_startup_migrates_cached_resource_shortcut(app, mocker, monkeypatch, tmp_path):
    from nonebot_plugin_alconna import command_manager

    from nonebot_plugin_skland import hook
    from nonebot_plugin_skland.matcher import skland, skland_command
    from nonebot_plugin_skland.services.resources import ResourceUpdateResult

    original_cache = tmp_path / "original-shortcuts.db"
    command_manager.dump_cache(original_cache, command=skland_command)
    monkeypatch.setattr(hook, "shortcut_cache", tmp_path / "legacy-shortcuts.db")
    monkeypatch.setattr(hook.config, "check_res_update", True)
    mocker.patch.object(
        hook,
        "update_data_resources",
        new=mocker.AsyncMock(return_value=ResourceUpdateResult(messages=("明日方舟数据资源更新失败",), failed=True)),
    )
    mocker.patch.object(hook, "download_img_resource", new=mocker.AsyncMock())
    try:
        skland_command.shortcut("资源更新", delete=True)
        skland.shortcut("资源更新", {"command": "skland sync", "fuzzy": True, "prefix": True})
        command_manager.dump_cache(hook.shortcut_cache, command=skland_command)
        skland_command.shortcut("资源更新", delete=True)
        command_manager.records.clear()

        await hook.startup()

        for text in ("/资源更新", "/资源更新 --force", "/资源更新   --force"):
            result = skland_command.parse(text)
            assert result.matched, result.error_info
            assert result.find("sync.data")
            assert not result.find("sync.img")
            assert bool(result.find("sync.force")) == ("--force" in text)
        assert not skland_command.parse("/资源更新--force").matched
        bare = skland_command.parse("/skland sync")
        assert bare.matched
        assert not bare.find("sync.data")
        assert not bare.find("sync.img")
        image_only = skland_command.parse("/skland sync --img")
        assert image_only.matched
        assert image_only.find("sync.img")
        assert not image_only.find("sync.data")
    finally:
        command_manager.delete_shortcut(skland_command)
        command_manager.load_cache(original_cache, command=skland_command)
        command_manager.records.clear()
