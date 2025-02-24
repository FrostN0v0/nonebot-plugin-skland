from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_user")
require("nonebot_plugin_orm")
from nonebot_plugin_user import UserSession
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_alconna import (
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
from .schemas import CRED
from .exception import RequestException
from .api import SklandAPI, SklandLoginAPI
from .db_handler import get_arknights_characters, get_arknights_character_by_uid
from .utils import get_characters_and_bind, refresh_cred_token_if_needed, refresh_access_token_if_needed

__plugin_meta__ = PluginMetadata(
    name="明日方舟数据查询",
    description="通过森空岛查询游戏数据",
    usage="/skland",
    type="application",
    homepage="https://github.com/FrostN0v0/nonebot-plugin-skland",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra={
        "author": "FrostN0v0 <1614591760@qq.com>",
        "version": "0.1.0",
    },
)

skland = on_alconna(
    Alconna(
        "skland",
        Subcommand(
            "-b|--bind|bind",
            Args["token", str, Field(completion=lambda: "请输入 token 或 cred 完成绑定")],
            Option(
                "-u|--update|update",
            ),
            help_text="绑定森空岛账号",
        ),
        Subcommand(
            "arksign",
            Option(
                "-u|--uid|uid",
                Args["uid", str, Field(completion=lambda: "请输入指定绑定角色uid")],
            ),
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


@skland.assign("$main")
async def _():
    await UniMessage("").send()


@skland.assign("bind")
async def _(
    token: Match[str],
    result: Arparma,
    user_session: UserSession,
    msg_target: MsgTarget,
    session: async_scoped_session,
):
    if user := await session.get(User, user_session.user_id):
        if result.find("bind.update"):
            if len(token.result) == 24:
                grant_code = await SklandLoginAPI.get_grant_code(token.result)
                cred = await SklandLoginAPI.get_cred(grant_code)
                user.access_token = token.result
                user.cred = cred.cred
                user.cred_token = cred.token
            elif len(token.result) == 32:
                cred = await SklandLoginAPI.refresh_token(token.result)
                user.cred = cred.cred
                user.cred_token = cred.token
            else:
                await UniMessage("token 或 cred 错误,请检查格式").finish(at_sender=True)
            await session.commit()
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
                )
            elif len(token.result) == 32:
                cred = await SklandLoginAPI.refresh_token(token.result)
                user = User(
                    cred=cred.cred,
                    cred_token=cred.token,
                    id=user_session.user_id,
                )
            else:
                await UniMessage("token 或 cred 错误,请检查格式").finish(at_sender=True)
            session.add(user)
            await get_characters_and_bind(user, session)
            await UniMessage("绑定成功").finish(at_sender=True)
        except RequestException as e:
            await UniMessage(f"绑定失败,错误信息:{e}").finish(at_sender=True)


@skland.assign("arksign")
async def _(user_session: UserSession, session: async_scoped_session, uid: Match[str]):
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

    if uid.available:
        character = await get_arknights_character_by_uid(user, uid.result, session)
        sign_result = await sign_in(user, uid.result, character.channel_master_id)
    else:
        ark_characters = await get_arknights_characters(user, session)
        if not ark_characters:
            await UniMessage("未绑定 arknights 账号").finish(at_sender=True)

        char = ark_characters[0]
        sign_result = await sign_in(user, str(char.uid), char.channel_master_id)

    if sign_result:
        await UniMessage(
            f"角色: {char.nickname} 签到成功，获得了:\n"
            + "\n".join(f"{award.resource.name} x {award.count}" for award in sign_result.awards)
        ).send(at_sender=True)

    await session.commit()
