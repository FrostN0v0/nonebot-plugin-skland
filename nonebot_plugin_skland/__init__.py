"""
nonebot-plugin-skland

通过森空岛查询游戏数据
"""

from nonebot import require
from nonebot.adapters import Bot
from nonebot.params import Depends
from nonebot.permission import SuperUser
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_orm")
require("nonebot_plugin_user")
require("nonebot_plugin_argot")
require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
require("nonebot_plugin_htmlrender")
require("nonebot_plugin_apscheduler")
require("nonebot_plugin_waiter")

from nonebot_plugin_user import UserSession
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_alconna import At, Match, MsgId, Arparma, MsgTarget
from nonebot_plugin_alconna.builtins.extensions import ReplyRecordExtension

from . import hook as hook
from .config import Config
from .matcher import skland
from .extras import extra_data
from . import tasks as tasks  # noqa: F401

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
        "version": "0.7.2",
    },
)
__plugin_meta__.extra.update(extra_data)


@skland.assign("role", or_not=True)
async def _(session: async_scoped_session, user_session: UserSession, target: Match[At | int], result: Arparma):
    """角色卡片查询"""
    from .commands.card import card_handler

    if result.subcommands:
        await skland.finish("请将 -r/--role 放在需要选角的具体子命令后使用")
    await card_handler(session, user_session, target, role_index=result.query("role.role_index"))


@skland.assign("bind")
async def _(
    token: Match[str],
    result: Arparma,
    user_session: UserSession,
    msg_target: MsgTarget,
    session: async_scoped_session,
):
    """绑定森空岛账号"""
    from .commands.bind import bind_handler

    await bind_handler(token, result, user_session, msg_target, session)


@skland.assign("qrcode")
async def _(user_session: UserSession, session: async_scoped_session):
    """二维码绑定森空岛账号"""
    from .commands.bind import qrcode_handler

    await qrcode_handler(user_session, session)


@skland.assign("unbind")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
):
    """解绑森空岛账号"""
    from .commands.bind import unbind_handler

    await unbind_handler(user_session, session)


@skland.assign("arksign.sign")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
    result: Arparma,
):
    """明日方舟森空岛签到"""
    from .commands.arksign import arksign_sign_handler

    await arksign_sign_handler(user_session, session, result.query("arksign.sign.role.role_index"), result)


@skland.assign("arksign.status")
async def arksign_status(
    user_session: UserSession,
    session: async_scoped_session,
    bot: Bot,
    result: Arparma,
    is_superuser: bool = Depends(SuperUser()),
):
    """查看签到状态"""
    from .commands.arksign import arksign_status_handler

    await arksign_status_handler(
        user_session, session, bot, result, is_superuser, role_index=result.query("arksign.status.role.role_index")
    )


@skland.assign("arksign.all")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
    bot: Bot,
    is_superuser: bool = Depends(SuperUser()),
):
    """签到所有绑定角色"""
    from .commands.arksign import arksign_all_handler

    await arksign_all_handler(user_session, session, bot, is_superuser)


@skland.assign("char")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
    result: Arparma,
    is_superuser: bool = Depends(SuperUser()),
):
    """Manage Skland accounts and default roles."""
    from .commands.char import char_handler

    await char_handler(user_session, session, result, is_superuser)


@skland.assign("sync")
async def _(
    user_session: UserSession,
    result: Arparma,
    is_superuser: bool = Depends(SuperUser()),
):
    """同步游戏资源"""
    from .commands.sync import sync_handler

    await sync_handler(user_session, result, is_superuser)


@skland.assign("rogue")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
    result: Arparma,
    target: Match[At | int],
):
    """获取明日方舟肉鸽战绩"""
    from .commands.rogue import rogue_handler

    await rogue_handler(user_session, session, result, target, role_index=result.query("rogue.role.role_index"))


@skland.assign("rginfo")
async def _(
    id: Match[int],
    msg_id: MsgId,
    ext: ReplyRecordExtension,
    result: Arparma,
    user_session: UserSession,
    session: async_scoped_session,
):
    """获取明日方舟肉鸽战绩详情"""
    from .commands.rogue import rginfo_handler

    await rginfo_handler(
        id, msg_id, ext, result, user_session, session, role_index=result.query("rginfo.role.role_index")
    )


@skland.assign("gacha")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
    begin: Match[int],
    limit: Match[int],
    target: Match[At | int],
    bot: Bot,
    result: Arparma,
):
    """查询明日方舟抽卡记录"""
    from .commands.gacha import gacha_handler

    await gacha_handler(
        user_session, session, begin, limit, target, bot, role_index=result.query("gacha.role.role_index")
    )


@skland.assign("import")
async def _(url: Match[str], user_session: UserSession, session: async_scoped_session, result: Arparma):
    """导入明日方舟抽卡记录"""
    from .commands.gacha import import_handler

    await import_handler(url, user_session, session, role_index=result.query("import.role.role_index"))


@skland.assign("efsign.sign")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
    result: Arparma,
):
    """终末地森空岛签到"""
    from .commands.endfield import ef_sign_handler

    await ef_sign_handler(user_session, session, result.query("efsign.sign.role.role_index"), result)


@skland.assign("efsign.status")
async def efsign_status(
    user_session: UserSession,
    session: async_scoped_session,
    bot: Bot,
    result: Arparma,
    is_superuser: bool = Depends(SuperUser()),
):
    """查看终末地签到状态"""
    from .commands.endfield import ef_sign_status_handler

    await ef_sign_status_handler(
        user_session, session, bot, result, is_superuser, role_index=result.query("efsign.status.role.role_index")
    )


@skland.assign("efsign.all")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
    bot: Bot,
    is_superuser: bool = Depends(SuperUser()),
):
    """签到所有终末地绑定角色"""
    from .commands.endfield import ef_sign_all_handler

    await ef_sign_all_handler(user_session, session, bot, is_superuser)


@skland.assign("efcard")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
    target: Match[At | int],
    result: Arparma,
):
    """查询终末地绑定角色"""
    from .commands.endfield import efcard_handler

    show_all = result.find("efcard.all")
    is_simple = result.find("efcard.simple")
    await efcard_handler(
        user_session, session, target, show_all, is_simple, role_index=result.query("efcard.role.role_index")
    )


@skland.assign("efwar")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
    target: Match[At | int],
    season_id: Match[int],
    week_id: Match[int],
    result: Arparma,
):
    """查询终末地战争回响战绩"""
    from .commands.endfield import ef_war_echoes_handler

    await ef_war_echoes_handler(
        user_session,
        session,
        target,
        role_index=result.query("efwar.role.role_index"),
        season_id=season_id.result if season_id.available else None,
        week_id=week_id.result if week_id.available else None,
    )


@skland.assign("efgacha")
async def _(
    user_session: UserSession,
    session: async_scoped_session,
    begin: Match[int],
    limit: Match[int],
    target: Match[At | int],
    bot: Bot,
    result: Arparma,
):
    """查询终末地抽卡记录"""
    from .commands.endfield import ef_gacha_history_handler

    await ef_gacha_history_handler(
        user_session, session, begin, limit, target, bot, role_index=result.query("efgacha.role.role_index")
    )


@skland.assign("box")
async def _(
    session: async_scoped_session,
    user_session: UserSession,
    target: Match[At | int],
    filters: Match[tuple[str, ...]],
    ownership: Match[str],
    rarities: Match[str],
    professions: Match[str],
    branches: Match[str],
    positions: Match[str],
    genders: Match[str],
    factions: Match[str],
    races: Match[str],
    potentials: Match[str],
    name: Match[str],
    sort: Match[str],
    bot: Bot,
    result: Arparma,
):
    """明日方舟干员查询"""
    from .commands.box import box_handler

    await box_handler(
        session,
        user_session,
        target,
        filters,
        ownership,
        rarities,
        professions,
        branches,
        positions,
        genders,
        factions,
        races,
        potentials,
        name,
        sort,
        bot,
        role_index=result.query("box.role.role_index"),
    )
