import json
import asyncio
from io import BytesIO
from datetime import datetime, timedelta

import qrcode
from nonebot.adapters import Bot
from nonebot.params import Depends
from nonebot import logger, require
from nonebot.permission import SuperUser
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_orm")
require("nonebot_plugin_user")
require("nonebot_plugin_argot")
require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
require("nonebot_plugin_htmlrender")
require("nonebot_plugin_apscheduler")
from arclet.alconna import config as alc_config
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_argot.data_source import get_argot
from nonebot_plugin_argot import Text, Argot, Image, ArgotExtension
from nonebot_plugin_orm import get_scoped_session, async_scoped_session
from nonebot_plugin_alconna.builtins.extensions import ReplyRecordExtension
from nonebot_plugin_alconna import (
    At,
    Args,
    Field,
    Match,
    MsgId,
    Option,
    Alconna,
    Arparma,
    MsgTarget,
    Namespace,
    CustomNode,
    Subcommand,
    UniMessage,
    CommandMeta,
    on_alconna,
    message_reaction,
)

from .model import User
from . import hook as hook
from .extras import extra_data
from .exception import RequestException
from .api import SklandAPI, SklandLoginAPI
from .download import GameResourceDownloader
from .schemas import CRED, Topics, RogueData, ArkSignResponse
from .config import CACHE_DIR, RESOURCE_ROUTES, Config, config
from .render import render_ark_card, render_rogue_card, render_rogue_info
from .db_handler import (
    select_all_users,
    get_arknights_characters,
    get_arknights_character_by_uid,
    get_default_arknights_character,
)
from .utils import (
    format_sign_result,
    get_background_image,
    get_characters_and_bind,
    get_rogue_background_image,
    refresh_cred_token_if_needed,
    refresh_access_token_if_needed,
    refresh_cred_token_with_error_return,
    refresh_access_token_with_error_return,
)

__plugin_meta__ = PluginMetadata(
    name="森空岛",
    description="通过森空岛查询游戏数据",
    usage="skland --help",
    config=Config,
    type="application",
    homepage="https://github.com/FrostN0v0/nonebot-plugin-skland",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra={
        "author": "FrostN0v0 <1614591760@qq.com>",
        "version": "0.4.2",
    },
)
__plugin_meta__.extra.update(extra_data)

ns = Namespace("skland", disable_builtin_options=set())
alc_config.namespaces["skland"] = ns

skland = on_alconna(
    Alconna(
        "skland",
        Args["target?#目标", At | int],
        Subcommand(
            "-b|--bind|bind",
            Args["token", str, Field(completion=lambda: "请输入 token 或 cred 完成绑定")],
            Option("-u|--update|update", help_text="更新绑定的 token 或 cred"),
            help_text="绑定森空岛账号",
        ),
        Subcommand("-q|--qrcode|qrcode", help_text="获取二维码进行扫码绑定"),
        Subcommand(
            "arksign",
            Subcommand(
                "sign",
                Option(
                    "-u|--uid|uid",
                    Args["uid", str, Field(completion=lambda: "请输入指定绑定角色uid")],
                    help_text="指定个人绑定的角色uid进行签到",
                ),
                Option("--all", help_text="签到所有个人绑定的角色"),
                help_text="个人绑定角色签到",
            ),
            Subcommand(
                "status",
                Option("--all", help_text="查看所有绑定角色签到状态(仅超管可用)"),
                help_text="查看绑定角色签到状态",
            ),
            Subcommand("all", help_text="签到所有绑定角色(仅超管可用)"),
            help_text="明日方舟森空岛签到相关功能",
        ),
        Subcommand("char", Option("-u|--update|update"), help_text="更新绑定角色信息"),
        Subcommand("sync", help_text="更新图片资源(仅超管可用)"),
        Subcommand(
            "rogue",
            Args["target?#目标", At | int],
            Option(
                "-t|--topic|topic",
                Args[
                    "topic_name#主题",
                    ["傀影", "水月", "萨米", "萨卡兹"],
                    Field(completion=lambda: "请输入指定topic_id"),
                ],
                help_text="指定主题进行肉鸽战绩查询",
            ),
            help_text="肉鸽战绩查询",
        ),
        Subcommand(
            "rginfo",
            Args["id#战绩ID", int, Field(completion=lambda: "请输入战绩ID进行查询")],
            Option("-f|--favored|favored", help_text="是否查询收藏的战绩"),
            help_text="查询单局肉鸽战绩详情",
        ),
        namespace=alc_config.namespaces["skland"],
        meta=CommandMeta(
            description=__plugin_meta__.description,
            usage=__plugin_meta__.usage,
            example="/skland",
        ),
    ),
    comp_config={"lite": True},
    skip_for_unmatch=False,
    use_cmd_start=True,
    extensions=[ArgotExtension, ReplyRecordExtension],
)

skland.shortcut("森空岛绑定", {"command": "skland bind", "fuzzy": True, "prefix": True})
skland.shortcut("扫码绑定", {"command": "skland qrcode", "fuzzy": False, "prefix": True})
skland.shortcut("明日方舟签到", {"command": "skland arksign sign --all", "fuzzy": False, "prefix": True})
skland.shortcut("签到详情", {"command": "skland arksign status", "fuzzy": False, "prefix": True})
skland.shortcut("全体签到", {"command": "skland arksign all", "fuzzy": False, "prefix": True})
skland.shortcut("全体签到详情", {"command": "skland arksign status --all", "fuzzy": False, "prefix": True})
skland.shortcut(
    "萨卡兹肉鸽",
    {"command": "skland rogue --topic 萨卡兹", "fuzzy": False, "prefix": True},
)
skland.shortcut("萨米肉鸽", {"command": "skland rogue --topic 萨米", "fuzzy": False, "prefix": True})
skland.shortcut("水月肉鸽", {"command": "skland rogue --topic 水月", "fuzzy": False, "prefix": True})
skland.shortcut("傀影肉鸽", {"command": "skland rogue --topic 傀影", "fuzzy": False, "prefix": True})
skland.shortcut("角色更新", {"command": "skland char update", "fuzzy": False, "prefix": True})
skland.shortcut("资源更新", {"command": "skland sync", "fuzzy": False, "prefix": True})
skland.shortcut("战绩详情", {"command": "skland rginfo", "fuzzy": True, "prefix": True})
skland.shortcut("收藏战绩详情", {"command": "skland rginfo -f", "fuzzy": True, "prefix": True})


@skland.assign("$main")
async def _(session: async_scoped_session, user_session: UserSession, target: Match[At | int]):
    @refresh_cred_token_if_needed
    @refresh_access_token_if_needed
    async def get_character_info(user: User, uid: str):
        return await SklandAPI.ark_card(CRED(cred=user.cred, token=user.cred_token), uid)

    if target.available:
        target_platform_id = target.result.target if isinstance(target.result, At) else target.result
        target_id = (await get_user(user_session.platform, str(target_platform_id))).id
    else:
        target_id = user_session.user_id

    user = await session.get(User, target_id)
    if not user:
        await UniMessage("未绑定 skland 账号").finish(at_sender=True)
    ark_characters = await get_default_arknights_character(user, session)
    if not ark_characters:
        await UniMessage("未绑定 arknights 账号").finish(at_sender=True)
    if user_session.platform == "QQClient":
        await message_reaction("66")
    else:
        await message_reaction("❤")

    info = await get_character_info(user, str(ark_characters.uid))
    if not info:
        return
    background = await get_background_image()
    image = await render_ark_card(info, background)
    if str(background).startswith("http"):
        argot_seg = [Text(str(background)), Image(url=str(background))]
    else:
        argot_seg = Image(path=str(background))
    msg = UniMessage.image(raw=image) + Argot(
        "background", argot_seg, command="background", expired_at=config.argot_expire
    )
    await msg.send(reply_to=True)
    await session.commit()


@skland.assign("bind")
async def _(
    token: Match[str],
    result: Arparma,
    user_session: UserSession,
    msg_target: MsgTarget,
    session: async_scoped_session,
):
    """绑定森空岛账号"""

    if not msg_target.private:
        await UniMessage("绑定指令只允许在私聊中使用").finish(at_sender=True)

    if user := await session.get(User, user_session.user_id):
        if result.find("bind.update"):
            if len(token.result) == 24:
                grant_code = await SklandLoginAPI.get_grant_code(token.result)
                cred = await SklandLoginAPI.get_cred(grant_code)
                user.access_token = token.result
                user.cred = cred.cred
                user.cred_token = cred.token
            elif len(token.result) == 32:
                cred_token = await SklandLoginAPI.refresh_token(token.result)
                user.cred = token.result
                user.cred_token = cred_token
            else:
                await UniMessage("token 或 cred 错误,请检查格式").finish(at_sender=True)
            await get_characters_and_bind(user, session)
            await UniMessage("更新成功").finish(at_sender=True)
        await UniMessage("已绑定过 skland 账号").finish(at_sender=True)

    if token.available:
        try:
            if len(token.result) == 24:
                grant_code = await SklandLoginAPI.get_grant_code(token.result)
                cred = await SklandLoginAPI.get_cred(grant_code)
                user = User(
                    access_token=token.result,
                    cred=cred.cred,
                    cred_token=cred.token,
                    id=user_session.user_id,
                    user_id=cred.userId,
                )
            elif len(token.result) == 32:
                cred_token = await SklandLoginAPI.refresh_token(token.result)
                user_id = await SklandAPI.get_user_ID(CRED(cred=token.result, token=cred_token))
                user = User(
                    cred=token.result,
                    cred_token=cred_token,
                    id=user_session.user_id,
                    user_id=user_id,
                )
            else:
                await UniMessage("token 或 cred 错误,请检查格式").finish(at_sender=True)
            session.add(user)
            await get_characters_and_bind(user, session)
            await UniMessage("绑定成功").finish(at_sender=True)
        except RequestException as e:
            await UniMessage(f"绑定失败,错误信息:{e}").finish(at_sender=True)


@skland.assign("qrcode")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
):
    """二维码绑定森空岛账号"""
    scan_id = await SklandLoginAPI.get_scan()
    scan_url = f"hypergryph://scan_login?scanId={scan_id}"
    qr_code = qrcode.make(scan_url)
    result_stream = BytesIO()
    qr_code.save(result_stream, "PNG")
    msg = UniMessage("请使用森空岛app扫描二维码绑定账号\n二维码有效时间两分钟，请不要扫描他人的登录二维码进行绑定~")
    msg += UniMessage.image(raw=result_stream.getvalue())
    qr_msg = await msg.send(reply_to=True)
    end_time = datetime.now() + timedelta(seconds=100)
    scan_code = None
    while datetime.now() < end_time:
        try:
            scan_code = await SklandLoginAPI.get_scan_status(scan_id)
            break
        except RequestException:
            pass
        await asyncio.sleep(2)
    if qr_msg.recallable:
        await qr_msg.recall(index=0)
    if scan_code:
        if user_session.platform == "QQClient":
            await message_reaction("124")
        else:
            await message_reaction("👌")
        token = await SklandLoginAPI.get_token_by_scan_code(scan_code)
        grant_code = await SklandLoginAPI.get_grant_code(token)
        cred = await SklandLoginAPI.get_cred(grant_code)
        if user := await session.get(User, user_session.user_id):
            user.access_token = token
            user.cred = cred.cred
            user.cred_token = cred.token
        else:
            user = User(
                access_token=token,
                cred=cred.cred,
                cred_token=cred.token,
                id=user_session.user_id,
                user_id=cred.userId,
            )
            session.add(user)
        await get_characters_and_bind(user, session)
        await UniMessage("绑定成功").finish(at_sender=True)
    else:
        await UniMessage("二维码超时,请重新获取并扫码").finish(at_sender=True)


@skland.assign("arksign.sign")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
    uid: Match[str],
    result: Arparma,
):
    """明日方舟森空岛签到"""

    @refresh_cred_token_if_needed
    @refresh_access_token_if_needed
    async def sign_in(user: User, uid: str, channel_master_id: str):
        """执行签到逻辑"""
        cred = CRED(cred=user.cred, token=user.cred_token)
        return await SklandAPI.ark_sign(cred, uid, channel_master_id=channel_master_id)

    user = await session.get(User, user_session.user_id)
    if not user:
        await UniMessage("未绑定 skland 账号").finish(at_sender=True)

    sign_result: dict[str, ArkSignResponse] = {}
    if uid.available:
        character = await get_arknights_character_by_uid(user, uid.result, session)
        sign_result[character.nickname] = await sign_in(user, uid.result, character.channel_master_id)
    else:
        if result.find("arksign.sign.all"):
            characters = await get_arknights_characters(user, session)
            for character in characters:
                sign_result[character.nickname] = await sign_in(user, str(character.uid), character.channel_master_id)
        else:
            character = await get_default_arknights_character(user, session)
            if not character:
                await UniMessage("未绑定 arknights 账号").finish(at_sender=True)

            sign_result[character.nickname] = await sign_in(user, str(character.uid), character.channel_master_id)

    if sign_result:
        await UniMessage(
            "\n".join(
                f"角色: {nickname} 签到成功，获得了:\n"
                + "\n".join(f"{award.resource.name} x {award.count}" for award in sign.awards)
                for nickname, sign in sign_result.items()
            )
        ).send(at_sender=True)

    await session.commit()


@skland.assign("char.update")
async def _(user_session: UserSession, session: async_scoped_session):
    """更新森空岛角色信息"""

    @refresh_cred_token_if_needed
    @refresh_access_token_if_needed
    async def refresh_characters(user: User):
        await get_characters_and_bind(user, session)
        await UniMessage("更新成功").send(at_sender=True)

    if user := await session.get(User, user_session.user_id):
        await refresh_characters(user)


@skland.assign("sync")
async def _(is_superuser: bool = Depends(SuperUser())):
    if not is_superuser:
        await UniMessage.text("该指令仅超管可用").finish()
    try:
        logger.info("开始下载游戏资源")
        for route in RESOURCE_ROUTES:
            logger.info(f"正在下载: {route}")
            await GameResourceDownloader.download_all(
                owner="yuanyan3060",
                repo="ArknightsGameResource",
                route=route,
                branch="main",
            )
        version = await GameResourceDownloader.get_version()
        GameResourceDownloader.update_version_file(version)
        await UniMessage.text(f"资源更新成功，版本:{version}").send()
    except RequestException as e:
        logger.error(f"下载游戏资源失败: {e}")
        await UniMessage.text(f"资源更新失败：{e.args[0]}").send()


@skland.assign("rogue")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
    result: Arparma,
    target: Match[At | int],
):
    """获取明日方舟肉鸽战绩"""

    @refresh_cred_token_if_needed
    @refresh_access_token_if_needed
    async def get_rogue_info(user: User, uid: str, topic_id: str):
        return await SklandAPI.get_rogue(
            CRED(cred=user.cred, token=user.cred_token, userId=str(user.user_id)),
            uid,
            topic_id,
        )

    if target.available:
        target_platform_id = target.result.target if isinstance(target.result, At) else target.result
        target_id = (await get_user(user_session.platform, str(target_platform_id))).id
    else:
        target_id = user_session.user_id

    user = await session.get(User, target_id)
    if not user:
        await UniMessage("未绑定 skland 账号").finish(at_sender=True)
    character = await get_default_arknights_character(user, session)
    if not character:
        await UniMessage("未绑定 arknights 账号").finish(at_sender=True)
    if user_session.platform == "QQClient":
        await message_reaction("66")
    else:
        await message_reaction("❤")

    topic_id = Topics(str(result.query("rogue.topic.topic_name"))).topic_id if result.find("rogue.topic") else ""
    rogue = await get_rogue_info(user, str(character.uid), topic_id)
    background = await get_rogue_background_image(topic_id)
    img = await render_rogue_card(rogue, background)
    if str(background).startswith("http"):
        argot_seg = [Text(str(background)), Image(url=str(background))]
    else:
        argot_seg = Image(path=str(background))
    await UniMessage(
        Image(raw=img)
        + Argot("data", rogue.model_dump_json(), command=False)
        + Argot("background", argot_seg, command="background", expired_at=config.argot_expire)
    ).send()
    await session.commit()


@skland.assign("rginfo")
async def _(id: Match[int], msg_id: MsgId, ext: ReplyRecordExtension, result: Arparma, user_session: UserSession):
    """获取明日方舟肉鸽战绩详情"""
    if reply := ext.get_reply(msg_id):
        argot = await get_argot("data", reply.id)
        if not argot:
            if user_session.platform == "QQClient":
                await message_reaction("326")
            else:
                await message_reaction("🤖")
            await UniMessage.text("未找到该暗语或暗语已过期").finish(at_sender=True)
        if data := argot.dump_segment():
            if user_session.platform == "QQClient":
                await message_reaction("66")
            else:
                await message_reaction("❤")
            rogue_data = RogueData.model_validate_json(UniMessage.load(data).extract_plain_text())
            background = await get_rogue_background_image(rogue_data.topic)
            if result.find("rginfo.favored"):
                img = await render_rogue_info(rogue_data, background, id.result, True)
            else:
                img = await render_rogue_info(rogue_data, background, id.result, False)
            if str(background).startswith("http"):
                argot_seg = [Text(str(background)), Image(url=str(background))]
            else:
                argot_seg = Image(path=str(background))
            await UniMessage(
                Image(raw=img) + Argot("background", argot_seg, command="background", expired_at=config.argot_expire)
            ).send()
    else:
        await UniMessage.text("请回复一条肉鸽战绩").finish()


@skland.assign("arksign.status")
async def arksign_status(
    user_session: UserSession,
    session: async_scoped_session,
    bot: Bot,
    result: Arparma | bool,
    is_superuser: bool = Depends(SuperUser()),
):
    sign_result_file = CACHE_DIR / "sign_result.json"
    sign_result = {}
    sign_data = {}
    if not sign_result_file.exists():
        await UniMessage.text("未找到签到结果").finish()
    else:
        with open(sign_result_file, encoding="utf-8") as f:
            sign_result = json.load(f)
    sign_data = sign_result.get("data", {})
    sign_time = sign_result.get("timestamp", "未记录签到时间")
    if isinstance(result, Arparma) and result.find("arksign.status.all"):
        if not is_superuser:
            await UniMessage.text("该指令仅超管可用").finish()
    elif isinstance(result, bool) and result:
        if not is_superuser:
            await UniMessage.text("该指令仅超管可用").finish()
    else:
        user = await session.get(User, user_session.user_id)
        if not user:
            await UniMessage("未绑定 skland 账号").finish(at_sender=True)
        chars = await get_arknights_characters(user, session)
        char_nicknames = {char.nickname for char in chars}
        sign_data = {nickname: value for nickname, value in sign_data.items() if nickname in char_nicknames}
    if user_session.platform == "QQClient":
        await message_reaction("66")
        sliced_nodes = []
        prased_sign_result = format_sign_result(sign_data, sign_time, False)
        NODE_SLICE_LIMIT = 98
        formatted_nodes = {k: f"{v}\n" for k, v in prased_sign_result.results.items()}
        for i in range(0, len(formatted_nodes.items()), NODE_SLICE_LIMIT):
            sliced_node_items = list(formatted_nodes.items())[i : i + NODE_SLICE_LIMIT]
            sliced_nodes.append(dict(sliced_node_items))
        for index, node in enumerate(sliced_nodes):
            if index == 0:
                await UniMessage.reference(
                    CustomNode(bot.self_id, "签到结果", prased_sign_result.summary),
                    *[CustomNode(bot.self_id, nickname, content) for nickname, content in node.items()],
                ).send()
            else:
                await UniMessage.reference(
                    *[CustomNode(bot.self_id, nickname, content) for nickname, content in node.items()],
                ).send()
    else:
        await message_reaction("❤")
        prased_sign_result = format_sign_result(sign_data, sign_time, True)
        formatted_messages = [prased_sign_result.results[nickname] for nickname in prased_sign_result.results]
        await UniMessage.text(prased_sign_result.summary + "\n".join(formatted_messages)).finish()


@refresh_cred_token_with_error_return
@refresh_access_token_with_error_return
async def sign_in(user: User, uid: str, channel_master_id: str) -> ArkSignResponse | str:
    """执行签到逻辑"""
    cred = CRED(cred=user.cred, token=user.cred_token)
    return await SklandAPI.ark_sign(cred, uid, channel_master_id=channel_master_id)


@skland.assign("arksign.all")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
    bot: Bot,
    is_superuser: bool = Depends(SuperUser()),
):
    """签到所有绑定角色"""
    if not is_superuser:
        await UniMessage.text("该指令仅超管可用").finish()
    if user_session.platform == "QQClient":
        await message_reaction("66")
    else:
        await message_reaction("❤")
    sign_result: dict[str, ArkSignResponse | str] = {}
    serializable_sign_result: dict[str, dict | str] = {}
    for user in await select_all_users(session):
        characters = await get_arknights_characters(user, session)
        for character in characters:
            sign_result[character.nickname] = await sign_in(user, str(character.uid), character.channel_master_id)
    serializable_sign_result["data"] = {
        nickname: res.model_dump() if isinstance(res, ArkSignResponse) else res for nickname, res in sign_result.items()
    }
    serializable_sign_result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    sign_result_file = CACHE_DIR / "sign_result.json"
    if not sign_result_file.exists():
        sign_result_file.parent.mkdir(parents=True, exist_ok=True)
    with open(sign_result_file, "w", encoding="utf-8") as f:
        json.dump(serializable_sign_result, f, ensure_ascii=False, indent=2)
    await arksign_status(user_session, session, bot, True, is_superuser=is_superuser)


@scheduler.scheduled_job("cron", hour=0, minute=15, id="daily_arksign")
async def run_daily_arksign():
    session = get_scoped_session()
    sign_result: dict[str, ArkSignResponse | str] = {}
    serializable_sign_result: dict[str, dict | str] = {}
    for user in await select_all_users(session):
        characters = await get_arknights_characters(user, session)
        for character in characters:
            sign_result[character.nickname] = await sign_in(user, str(character.uid), character.channel_master_id)
    serializable_sign_result["data"] = {
        nickname: res.model_dump() if isinstance(res, ArkSignResponse) else res for nickname, res in sign_result.items()
    }
    serializable_sign_result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    sign_result_file = CACHE_DIR / "sign_result.json"
    if not sign_result_file.exists():
        sign_result_file.parent.mkdir(parents=True, exist_ok=True)
    with open(sign_result_file, "w", encoding="utf-8") as f:
        json.dump(serializable_sign_result, f, ensure_ascii=False, indent=2)
    await session.close()
