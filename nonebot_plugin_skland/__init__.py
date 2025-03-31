from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_orm")
require("nonebot_plugin_user")
require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
require("nonebot_plugin_htmlrender")
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_user import UserSession, get_user
from nonebot_plugin_alconna import (
    At,
    Args,
    Field,
    Match,
    Option,
    Alconna,
    Arparma,
    MsgTarget,
    Subcommand,
    UniMessage,
    CommandMeta,
    on_alconna,
)

from .model import User
from . import hook as hook
from .config import Config
from .render import render_ark_card
from .exception import RequestException
from .api import SklandAPI, SklandLoginAPI
from .schemas import CRED, Topics, ArkSignResponse
from .utils import get_characters_and_bind, refresh_cred_token_if_needed, refresh_access_token_if_needed
from .db_handler import get_arknights_characters, get_arknights_character_by_uid, get_default_arknights_character

__plugin_meta__ = PluginMetadata(
    name="森空岛",
    description="通过森空岛查询游戏数据",
    usage="/skland",
    config=Config,
    type="application",
    homepage="https://github.com/FrostN0v0/nonebot-plugin-skland",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna", "nonebot_plugin_user"),
    extra={
        "author": "FrostN0v0 <1614591760@qq.com>",
        "version": "0.1.4",
    },
)

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
        Subcommand(
            "arksign",
            Option(
                "-u|--uid|uid",
                Args["uid", str, Field(completion=lambda: "请输入指定绑定角色uid")],
                help_text="指定绑定角色uid进行签到",
            ),
            Option("--all", help_text="签到所有绑定角色"),
            help_text="明日方舟签到",
        ),
        Subcommand("char", Option("-u|--update|update"), help_text="更新绑定角色信息"),
        Subcommand(
            "rogue",
            Args["target?#目标", At | int],
            Option(
                "-t|--topic|topic",
                Args["topic_name?#主题", ["萨米", "萨卡兹"], Field(completion=lambda: "请输入指定topic_id")],
                help_text="指定主题进行肉鸽战绩查询",
            ),
            help_text="肉鸽战绩查询",
        ),
        meta=CommandMeta(
            description=__plugin_meta__.description,
            usage=__plugin_meta__.usage,
            example="/skland",
        ),
    ),
    comp_config={"lite": True},
    skip_for_unmatch=False,
    block=True,
    use_cmd_start=True,
)

skland.shortcut("森空岛绑定", {"command": "skland bind", "fuzzy": True, "prefix": True})
skland.shortcut("明日方舟签到", {"command": "skland arksign --all", "fuzzy": True, "prefix": True})
skland.shortcut("萨卡兹肉鸽", {"command": "skland rogue --topic 萨卡兹", "fuzzy": True, "prefix": True})
skland.shortcut("萨米肉鸽", {"command": "skland rogue --topic 萨米", "fuzzy": True, "prefix": True})
skland.shortcut("角色更新", {"command": "skland char update", "fuzzy": False, "prefix": True})


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

    info = await get_character_info(user, str(ark_characters.uid))
    image = await render_ark_card(info)
    await UniMessage.image(raw=image).send()
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

    if not msg_target.private:
        await UniMessage("绑定指令只允许在私聊中使用").finish(at_sender=True)

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


@skland.assign("arksign")
async def _(user_session: UserSession, session: async_scoped_session, uid: Match[str], result: Arparma):
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
        if result.find("arksign.all"):
            characters = await get_arknights_characters(user, session)
            for character in characters:
                sign_result[character.nickname] = await sign_in(user, str(character.uid), character.channel_master_id)
        else:
            character = await get_default_arknights_character(user, session)
            if not character:
                await UniMessage("未绑定 arknights 账号").finish(at_sender=True)

            sign_result[character.nickname] = await sign_in(user, str(character.uid), character.channel_master_id)

    if sign_result[character.nickname]:
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


@skland.assign("rogue")
async def _(user_session: UserSession, session: async_scoped_session, result: Arparma, target: Match[At | int]):
    """获取明日方舟肉鸽战绩"""

    # Not Finished
    @refresh_cred_token_if_needed
    @refresh_access_token_if_needed
    async def get_rogue_info(user: User, uid: str, topic_id: str):
        return await SklandAPI.get_rogue(
            CRED(cred=user.cred, token=user.cred_token, userId=str(user.user_id)), uid, topic_id
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

    topic_id = Topics(str(result.query("rogue.topic.topic_name"))).topic_id if result.find("rogue.topic") else ""
    # TODO: 渲染肉鸽战绩卡片，完善指令逻辑
    rogue = await get_rogue_info(user, str(character.uid), topic_id)  # noqa: F841
    # await UniMessage(rogue.model_dump_json()).send()
    await UniMessage("功能开发中（救命!来画渲染模板").send()
    await session.commit()
