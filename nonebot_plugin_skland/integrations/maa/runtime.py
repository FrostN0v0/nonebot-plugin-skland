"""QQ command and interaction handlers for the optional MAA integration."""

import asyncio
import sqlite3

from nonebot.matcher import Matcher
from nonebot.adapters import Bot, Event
from nonebot.permission import SUPERUSER
from nonebot_plugin_user import UserSession
from nonebot.adapters.qq import Bot as QQBot
from nonebot_plugin_alconna import Arparma, UniMessage
from nonebot import logger, get_bots, on_notice, get_driver
from nonebot.adapters.qq.exception import ActionFailed, NetworkError
from nonebot.adapters.qq import C2CMessageCreateEvent, InteractionCreateEvent, GroupMessageCreateEvent

from .matcher import control
from .notify import Notifications
from .binding_qq import BindingFlow
from . import admin_menu as admin_menu
from ...config import DATA_DIR, config
from .core import Store, RemoteError, digest
from .commands import Commands, validate_base_url
from .menu import Menus, page_for, keyboard_message

driver = get_driver()
store = Store(config.maa.data_dir or DATA_DIR / "maa")
commands = Commands(store, config.maa.public_url)
menus = Menus()
log = logger.bind(skland_maa=True)
notifications = Notifications(store, log)
binding_flow = BindingFlow(
    (config.maa.binding_state_dir or DATA_DIR / "maa-binding") / "pairing.sqlite3",
    config.maa.binding_socket,
    store,
    validate_base_url(config.maa.public_url),
    log,
)
workers: list[asyncio.Task] = []
log_sink: int | None = None


async def operate(send, bot, event, operation, argument, private, owner):
    if operation == "绑定":
        await binding_flow.command(send, bot, event, owner, private, argument)
        return
    if operation == "解绑" and private:
        await asyncio.to_thread(binding_flow.store.invalidate, owner)
    page = page_for(operation, private)
    if page:
        title, options = page
        nonce = menus.create(bot.self_id, event.get_user_id(), event.get_session_id(), private, owner, options)
        try:
            await send(keyboard_message(title, options, nonce))
        except (ActionFailed, NetworkError) as error:
            log.error(f"MAA keyboard send failure type={type(error).__name__}")
            await send("MAA 菜单发送失败，请管理员检查 QQ Markdown 和按钮消息权限。")
        return
    try:
        text, image = await asyncio.to_thread(
            commands.handle,
            operation,
            private,
            owner,
            event.event_id if isinstance(event, InteractionCreateEvent) else event.id,
            argument=argument,
            superuser=await SUPERUSER(bot, event) if operation == "证书" else False,
            origin={
                "bot_id": bot.self_id,
                "scene": "private" if private else "group",
                "target": event.get_user_id() if private else event.group_openid,
            },
        )
    except RemoteError as error:
        text, image = str(error), None
    try:
        await send(await UniMessage.text(text).export(bot=bot))
    except (ActionFailed, NetworkError) as error:
        log.error(f"MAA text send failure type={type(error).__name__}")
        return
    if image:
        try:
            await send(await UniMessage.image(path=image).export(bot=bot))
        except (ActionFailed, NetworkError) as error:
            log.error(f"MAA image send failure type={type(error).__name__}")
            await send("截图已取得，但 QQ 图片发送失败；可稍后重试 /MAA结果。")


@control.handle()
async def handle(matcher: Matcher, bot: Bot, event: Event, result: Arparma, user_session: UserSession):
    if not isinstance(bot, QQBot) or not isinstance(event, (C2CMessageCreateEvent, GroupMessageCreateEvent)):
        await matcher.finish("MAA 远控目前仅支持 QQ 官方 bot 的私聊与群聊。")
    owner = digest(f"{bot.self_id}:user:{user_session.user_id}")
    await operate(
        matcher.send,
        bot,
        event,
        result.main_args.get("operation") or "管理",
        result.main_args.get("argument") or "",
        isinstance(event, C2CMessageCreateEvent),
        owner,
    )


async def is_maa_callback(event: Event):
    return (
        isinstance(event, InteractionCreateEvent)
        and event.type == 11
        and (event.data.resolved.button_data or "").startswith("maamenu:")
    )


click = on_notice(rule=is_maa_callback, priority=4, block=True)


async def is_binding_callback(event: Event):
    return (
        isinstance(event, InteractionCreateEvent)
        and event.type == 11
        and (event.data.resolved.button_data or "").startswith("maabind:")
    )


binding_click = on_notice(rule=is_binding_callback, priority=3, block=True)


@binding_click.handle()
async def handle_binding_click(bot: QQBot, event: InteractionCreateEvent):
    await binding_flow.click(bot, event)


@click.handle()
async def handle_click(bot: QQBot, event: InteractionCreateEvent):
    if event.chat_type not in (1, 2):
        await bot.put_interaction(interaction_id=event.id, code=1)
        return
    selected = menus.claim(event.data.resolved.button_data, bot.self_id, event.get_user_id(), event.get_session_id())
    if not selected:
        await bot.put_interaction(interaction_id=event.id, code=1)
        return
    menu, command = selected
    try:
        await asyncio.wait_for(bot.put_interaction(interaction_id=event.id, code=0), timeout=3)
    except (ActionFailed, NetworkError, TimeoutError) as error:
        menu.claimed = False
        log.warning(f"MAA callback ACK failure type={type(error).__name__}")
        return
    sequence = 0

    async def send(message):
        nonlocal sequence
        sequence += 1
        if menu.private:
            return await bot.send_to_c2c(
                openid=event.user_openid, event_id=event.event_id, msg_seq=sequence, message=message
            )
        return await bot.send_to_group(
            group_openid=event.group_openid, event_id=event.event_id, msg_seq=sequence, message=message
        )

    # Buttons use the same parsed operations as Alconna commands.
    operation, _, argument = command[4:].strip().partition(" ")
    await operate(send, bot, event, operation or "管理", argument, menu.private, menu.owner)


async def maintenance():
    while True:
        try:
            await asyncio.to_thread(store.cleanup)
            log.info("MAA maintenance completed")
        except (OSError, sqlite3.Error) as error:
            log.error(f"MAA cleanup failure type={type(error).__name__}")
        await asyncio.sleep(3600)


async def notify_results():
    while True:
        try:
            await notifications.tick({key: bot for key, bot in get_bots().items() if isinstance(bot, QQBot)})
            await binding_flow.tick({key: bot for key, bot in get_bots().items() if isinstance(bot, QQBot)})
        except (OSError, sqlite3.Error) as error:
            log.error(f"MAA notification worker failure type={type(error).__name__}")
        await asyncio.sleep(2)


@driver.on_startup
async def startup():
    global log_sink
    await binding_flow.start()
    log_sink = logger.add(
        store.directory / "logs/maa.log",
        rotation="00:00",
        retention="3 days",
        encoding="utf-8",
        filter=lambda record: record["extra"].get("skland_maa", False),
    )
    workers.extend((asyncio.create_task(maintenance()), asyncio.create_task(notify_results())))


@driver.on_shutdown
async def shutdown():
    for task in workers:
        task.cancel()
    await asyncio.gather(*workers, return_exceptions=True)
    workers.clear()
    await binding_flow.close()
    if log_sink is not None:
        logger.remove(log_sink)
