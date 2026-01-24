import contextlib
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Literal, TypeVar, ParamSpec, Concatenate

import httpx
from pydantic import AnyUrl as Url
from nonebot import logger, get_driver
from nonebot_plugin_user import UserSession
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_alconna import UniMessage, message_reaction

from .api import SklandAPI, SklandLoginAPI
from .model import SkUser, Character, GachaRecord
from .download import DownloadResult, GameResourceDownloader
from .db_handler import select_user_characters, delete_character_gacha_records
from .exception import LoginException, RequestException, UnauthorizedException
from .config import RES_DIR, CACHE_DIR, RESOURCE_ROUTES, CustomSource, config, gacha_table_data
from .schemas import (
    CRED,
    GachaCate,
    GachaPool,
    GachaPull,
    GachaGroup,
    ArkSignResult,
    GroupedGachaRecord,
)

P = ParamSpec("P")
R = TypeVar("R")
Refreshable = Callable[Concatenate[SkUser, P], Coroutine[None, None, R]]


async def get_characters_and_bind(user: SkUser, session: async_scoped_session):
    cred = CRED(cred=user.cred, token=user.cred_token)
    binding_app_list = await SklandAPI.get_binding(cred)
    new_uids = {char.uid for app in binding_app_list for char in app.bindingList}
    for character in await select_user_characters(user, session):
        if character.uid not in new_uids:
            # 抽卡记录的外键引用了 skland_characters 表, 但未设置级联删除
            await delete_character_gacha_records(character, session)
            await session.delete(character)
    for app in binding_app_list:
        for character in app.bindingList:
            if character.roles:
                for role in character.roles:
                    await session.merge(
                        Character(
                            id=user.id,
                            uid=role.roleId,
                            nickname=role.nickname,
                            app_code=app.appCode,
                            channel_master_id=role.serverId,
                            isdefault=role.isDefault,
                        )
                    )
            else:
                await session.merge(
                    Character(
                        id=user.id,
                        uid=character.uid,
                        nickname=character.nickName,
                        app_code=app.appCode,
                        channel_master_id=character.channelMasterId,
                        isdefault=len(app.bindingList) == 1 or character.isDefault,
                    )
                )
    await session.commit()


def refresh_access_token_if_needed(func: Refreshable[P, R]) -> Refreshable[P, R | None]:
    """装饰器：如果 access_token 失效，刷新后重试"""

    async def wrapper(user: SkUser, *args: P.args, **kwargs: P.kwargs) -> R | None:
        try:
            return await func(user, *args, **kwargs)
        except LoginException:
            if not user.access_token:
                await UniMessage("cred失效，用户没有绑定token，无法自动刷新cred").send(at_sender=True)

            try:
                grant_code = await SklandLoginAPI.get_grant_code(user.access_token, 0)
                new_cred = await SklandLoginAPI.get_cred(grant_code)
                user.cred, user.cred_token = new_cred.cred, new_cred.token
                logger.info("access_token 失效，已自动刷新")
                return await func(user, *args, **kwargs)
            except (RequestException, LoginException, UnauthorizedException) as e:
                await UniMessage(f"接口请求失败,{e.args[0]}").send(at_sender=True)
        except RequestException as e:
            await UniMessage(f"接口请求失败,{e.args[0]}").send(at_sender=True)

    return wrapper


def refresh_cred_token_if_needed(func: Refreshable[P, R]) -> Refreshable[P, R | None]:
    """装饰器：如果 cred_token 失效，刷新后重试"""

    async def wrapper(user: SkUser, *args: P.args, **kwargs: P.kwargs) -> R | None:
        try:
            return await func(user, *args, **kwargs)
        except UnauthorizedException:
            try:
                new_token = await SklandLoginAPI.refresh_token(user.cred)
                user.cred_token = new_token
                logger.info("cred_token 失效，已自动刷新")
                return await func(user, *args, **kwargs)
            except (RequestException, LoginException, UnauthorizedException) as e:
                await UniMessage(f"接口请求失败,{e.args[0]}").send(at_sender=True)
        except RequestException as e:
            await UniMessage(f"接口请求失败,{e.args[0]}").send(at_sender=True)

    return wrapper


def refresh_cred_token_with_error_return(func: Refreshable[P, R]) -> Refreshable[P, R | str]:
    """装饰器：如果 cred_token 失效，刷新后重试"""

    async def wrapper(user: SkUser, *args: P.args, **kwargs: P.kwargs) -> R | str:
        try:
            return await func(user, *args, **kwargs)
        except UnauthorizedException:
            try:
                new_token = await SklandLoginAPI.refresh_token(user.cred)
                user.cred_token = new_token
                logger.info("cred_token 失效，已自动刷新")
                return await func(user, *args, **kwargs)
            except (RequestException, LoginException, UnauthorizedException) as e:
                return f"接口请求失败,{e.args[0]}"
        except RequestException as e:
            return f"接口请求失败,{e.args[0]}"

    return wrapper


def refresh_access_token_with_error_return(func: Refreshable[P, R]) -> Refreshable[P, R | str]:
    async def wrapper(user: SkUser, *args, **kwargs) -> R | str:
        try:
            return await func(user, *args, **kwargs)
        except LoginException:
            if not user.access_token:
                await UniMessage("cred失效，用户没有绑定token，无法自动刷新cred").send(at_sender=True)

            try:
                grant_code = await SklandLoginAPI.get_grant_code(user.access_token, 0)
                new_cred = await SklandLoginAPI.get_cred(grant_code)
                user.cred, user.cred_token = new_cred.cred, new_cred.token
                logger.info("access_token 失效，已自动刷新")
                return await func(user, *args, **kwargs)
            except (RequestException, LoginException, UnauthorizedException) as e:
                return f"接口请求失败,{e.args[0]}"
        except RequestException as e:
            return f"接口请求失败,{e.args[0]}"

    return wrapper


async def get_lolicon_image() -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.lolicon.app/setu/v2?tag=arknights")
    return response.json()["data"][0]["urls"]["original"]


async def get_background_image() -> str | Url:
    default_background = RES_DIR / "images" / "background" / "bg.jpg"

    match config.background_source:
        case "default":
            background_image = default_background.as_posix()
        case "Lolicon":
            background_image = await get_lolicon_image()
        case "random":
            background_image = CustomSource(uri=RES_DIR / "images" / "background").to_uri()
        case CustomSource() as cs:
            background_image = cs.to_uri()
        case _:
            background_image = default_background.as_posix()

    return background_image


async def get_rogue_background_image(rogue_id: str) -> str | Url:
    default_background = RES_DIR / "images" / "background" / "rogue" / "kv_epoque14.png"
    default_rogue_background_map = {
        "rogue_1": RES_DIR / "images" / "background" / "rogue" / "pic_rogue_1_KV1.png",
        "rogue_2": RES_DIR / "images" / "background" / "rogue" / "pic_rogue_2_50.png",
        "rogue_3": RES_DIR / "images" / "background" / "rogue" / "pic_rogue_3_KV2.png",
        "rogue_4": RES_DIR / "images" / "background" / "rogue" / "pic_rogue_4_47.png",
        "rogue_5": RES_DIR / "images" / "background" / "rogue" / "pic_rogue_5_KV1.png",
    }
    match config.rogue_background_source:
        case "default":
            background_image = default_background.as_posix()
        case "rogue":
            background_image = default_rogue_background_map.get(rogue_id, default_background).as_posix()
        case "Lolicon":
            background_image = await get_lolicon_image()
        case CustomSource() as cs:
            background_image = cs.to_uri()

    return background_image


def format_sign_result(sign_data: dict, sign_time: str, is_text: bool) -> ArkSignResult:
    """格式化签到结果"""
    formatted_results = {}
    success_count = 0
    failed_count = 0
    for nickname, result_data in sign_data.items():
        if isinstance(result_data, dict):
            awards_text = "\n".join(
                f"  {award['resource']['name']} x {award['count']}" for award in result_data["awards"]
            )
            if is_text:
                formatted_results[nickname] = f"✅ 角色：{nickname} 签到成功，获得了:\n📦{awards_text}"
            else:
                formatted_results[nickname] = f"✅ 签到成功，获得了:\n📦{awards_text}"
            success_count += 1
        elif isinstance(result_data, str):
            if "请勿重复签到" in result_data:
                if is_text:
                    formatted_results[nickname] = f"ℹ️ 角色：{nickname} 已签到 (无需重复签到)"
                else:
                    formatted_results[nickname] = "ℹ️ 已签到 (无需重复签到)"
                success_count += 1
            else:
                if is_text:
                    formatted_results[nickname] = f"❌ 角色：{nickname} 签到失败: {result_data}"
                else:
                    formatted_results[nickname] = f"❌ 签到失败: {result_data}"
                failed_count += 1
    return ArkSignResult(
        failed_count=failed_count,
        success_count=success_count,
        results=formatted_results,
        summary=(
            f"--- 签到结果概览 ---\n"
            f"总计签到角色: {len(formatted_results)}个\n"
            f"✅ 成功签到: {success_count}个\n"
            f"❌ 签到失败: {failed_count}个\n"
            f"⏰️ 签到时间: {sign_time}\n"
            f"--------------------"
        ),
    )


def format_endfield_sign_result(sign_data: dict, sign_time: str, is_text: bool) -> ArkSignResult:
    """格式化终末地签到结果"""
    formatted_results = {}
    success_count = 0
    failed_count = 0
    for nickname, result_data in sign_data.items():
        if isinstance(result_data, dict):
            # 终末地签到成功返回的数据结构
            resource_info_map = result_data.get("resourceInfoMap", {})
            award_ids = result_data.get("awardIds", [])
            award_lines = []
            for award in award_ids:
                info = resource_info_map.get(award["id"], {})
                name = info.get("name", "未知物品")
                count = info.get("count", 0)
                award_lines.append(f"  {name} x{count}")
            awards_text = "\n".join(award_lines)
            if is_text:
                formatted_results[nickname] = f"✅ 角色：{nickname} 签到成功，获得了:\n📦{awards_text}"
            else:
                formatted_results[nickname] = f"✅ 签到成功，获得了:\n📦{awards_text}"
            success_count += 1
        elif isinstance(result_data, str):
            if "请勿重复签到" in result_data:
                if is_text:
                    formatted_results[nickname] = f"ℹ️ 角色：{nickname} 已签到 (无需重复签到)"
                else:
                    formatted_results[nickname] = "ℹ️ 已签到 (无需重复签到)"
                success_count += 1
            else:
                if is_text:
                    formatted_results[nickname] = f"❌ 角色：{nickname} 签到失败: {result_data}"
                else:
                    formatted_results[nickname] = f"❌ 签到失败: {result_data}"
                failed_count += 1
    return ArkSignResult(
        failed_count=failed_count,
        success_count=success_count,
        results=formatted_results,
        summary=(
            f"--- 终末地签到结果概览 ---\n"
            f"总计签到角色: {len(formatted_results)}个\n"
            f"✅ 成功签到: {success_count}个\n"
            f"❌ 签到失败: {failed_count}个\n"
            f"⏰️ 签到时间: {sign_time}\n"
            f"--------------------"
        ),
    )


async def get_all_gacha_records(char: Character, cate: GachaCate, access_token: str, role_token: str, ak_cookie: str):
    """一个异步生成器，用于获取并逐条产出指定分类下的所有抽卡记录。

    此函数会自动处理分页，持续从森空岛(Skland)API请求数据，直到获取到
    指定卡池的全部抽卡记录为止。

    Args:
        uid (str): 用户的游戏角色唯一标识 (UID)。
        cate_id (str): 要查询的卡池类别ID，例如：'anniver_fest', 'summer_fest'。
        access_token (str): 用于验证 Skland API 的访问令牌 (access_token)。
        role_token (str): 用于验证的特定游戏角色令牌 (role_token)。
        ak_cookie (str): 所需的会话 Cookie 字符串。

    Yields:
        GachaInfo: 产出一个代表单次抽卡记录的对象。
                     其具体类型取决于 `SklandAPI.get_gacha_history` 返回结果中
                     `gacha_list` 内元素的结构。
    """
    page = await SklandAPI.get_gacha_history(char.uid, role_token, access_token, ak_cookie, cate.id)
    prev_ts, prev_pos = None, None

    while page and page.gacha_list:
        for record in page.gacha_list:
            yield record
        if not page.hasMore:
            break
        if (page.next_ts, page.next_pos) == (prev_ts, prev_pos):
            break
        prev_ts, prev_pos = page.next_ts, page.next_pos
        page = await SklandAPI.get_gacha_history(
            char.uid, role_token, access_token, ak_cookie, cate.id, gachaTs=page.next_ts, pos=page.next_pos
        )


def _get_up_chars(pool_id):
    """获取up五星和六星角色列表"""
    up_five_chars, up_six_chars = [], []
    for gacha_detail in gacha_table_data.gacha_details:
        if gacha_detail.gachaPoolId != pool_id:
            continue
        up_char = gacha_detail.gachaPoolDetail.detailInfo.upCharInfo
        avail_char = gacha_detail.gachaPoolDetail.detailInfo.availCharInfo
        if up_char and hasattr(up_char, "perCharList") and up_char.perCharList:
            for up_char_item in up_char.perCharList:
                if up_char_item.rarityRank == 4:
                    up_five_chars = up_char_item.charIdList
                elif up_char_item.rarityRank == 5:
                    up_six_chars = up_char_item.charIdList
        elif avail_char and hasattr(avail_char, "perAvailList") and avail_char.perAvailList:
            for avail_char_item in avail_char.perAvailList:
                if avail_char_item.rarityRank == 4:
                    up_five_chars = avail_char_item.charIdList
                elif avail_char_item.rarityRank == 5:
                    up_six_chars = avail_char_item.charIdList
    return up_five_chars, up_six_chars


def _get_pool_info(pool_id):
    """获取卡池开放时间、结束时间和规则类型"""
    for gacha_table in gacha_table_data.gacha_table:
        if gacha_table.gachaPoolId == pool_id:
            return gacha_table.openTime, gacha_table.endTime, gacha_table.gachaRuleType
    return 0, 0, 0


def group_gacha_records(records: list[GachaRecord]) -> GroupedGachaRecord:
    """将抽卡记录按卡池分组"""
    temp_grouped_records = defaultdict(lambda: defaultdict(list))
    for record in records:
        temp_grouped_records[record.pool_id][record.gacha_ts].append(record)
    final_pools_data: list[GachaPool] = []
    for pool_id, ts_dict in temp_grouped_records.items():
        up_five_chars, up_six_chars = _get_up_chars(pool_id)
        open_time, end_time, gacha_rule_type = _get_pool_info(pool_id)
        gacha_groups: list[GachaGroup] = [
            GachaGroup(
                gacha_ts=gacha_ts,
                pulls=[
                    GachaPull(
                        pool_name=p.pool_name,
                        char_id=p.char_id,
                        char_name=p.char_name,
                        rarity=p.rarity,
                        is_new=p.is_new,
                        pos=p.pos,
                    )
                    for p in pulls
                ],
            )
            for gacha_ts, pulls in ts_dict.items()
        ]
        gacha_pool = GachaPool(
            gachaPoolId=pool_id,
            gachaPoolName=gacha_groups[0].pulls[0].pool_name,
            openTime=open_time,
            endTime=end_time,
            up_five_chars=up_five_chars,
            up_six_chars=up_six_chars,
            gachaRuleType=gacha_rule_type,
            records=gacha_groups,
        )
        final_pools_data.append(gacha_pool)
    return GroupedGachaRecord(pools=final_pools_data)


async def import_heybox_gacha_data(url: str) -> dict:
    """导入Heybox导出的抽卡记录"""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code != 200:
            raise RequestException(f"请求失败，状态码：{response.status_code}")
        return response.json()


def get_char_id_by_char_name(char_name: str) -> str:
    """通过角色名称获取角色ID"""
    if char_name == "麒麟X夜刀":
        char_name = "麒麟R夜刀"
    return next(
        (char.char_id for char in gacha_table_data.character_table if char.name == char_name),
        "char_601_cguard",
    )


def get_pool_id(pool_name: str, gacha_ts: int) -> str:
    """通过卡池名称获取卡池ID"""
    special_pools = {
        "中坚寻访": [4, 6, 10],
        "标准寻访": [0, 9],
        "中坚甄选": [6],
        "联合行动": [0],
        "常驻标准寻访": [0],
        "【联合行动】特选干员定向寻访": [0],
        "进攻-防守-战术交汇": [2],
        "前路回响": [0],
    }
    for gacha_pool in gacha_table_data.gacha_table:
        if gacha_pool.gachaPoolName == pool_name and gacha_pool.openTime <= gacha_ts <= gacha_pool.endTime:
            return gacha_pool.gachaPoolId
        elif pool_name in special_pools:
            if (
                gacha_pool.gachaRuleType in special_pools[pool_name]
                and gacha_pool.openTime <= gacha_ts <= gacha_pool.endTime
            ):
                return gacha_pool.gachaPoolId
    return "NORM_1_0_1"


def heybox_data_to_record(data: dict, uid: int, char_id: int, char_uid: str) -> list[GachaRecord]:
    """将Heybox导出的抽卡记录转换为GachaRecord列表"""
    records: list[GachaRecord] = []
    for gacha_ts, gacha_data in data.items():
        pool_name = gacha_data["p"]
        pool_id = get_pool_id(pool_name, int(gacha_ts))
        if pool_id == "NORM_1_0_1":
            pool_name = "未知寻访"
        for index, char in enumerate(gacha_data["c"]):
            char_name = char[0]
            if char_name == "麒麟X夜刀":
                char_name = "麒麟R夜刀"
            records.append(
                GachaRecord(
                    uid=uid,
                    char_pk_id=char_id,
                    char_uid=char_uid,
                    pool_id=pool_id,
                    pool_name=pool_name,
                    char_id=get_char_id_by_char_name(char[0]),
                    char_name=char[0],
                    rarity=char[1],
                    is_new=char[2],
                    gacha_ts=int(gacha_ts),
                    pos=index,
                )
            )
    return records


def send_reaction(
    user_session: UserSession, emoji: Literal["fail", "done", "processing", "received", "unmatch"]
) -> None:
    emoji_map = {
        "fail": ["10060", "❌"],
        "done": ["144", "🎉"],
        "processing": ["66", "❤"],
        "received": ["124", "👌"],
        "unmatch": ["326", "🤖"],
    }

    async def send() -> None:
        with contextlib.suppress(Exception):
            await message_reaction(emoji_map[emoji][0] if user_session.platform == "QQClient" else emoji_map[emoji][1])

    get_driver().task_group.start_soon(send)


async def download_img_resource(
    force: bool,
    update: bool,
    user_session: UserSession | None = None,
) -> DownloadResult:
    """下载图片资源

    Args:
        force: 是否强制更新，忽略版本检查
        update: 是否更新替换已有图片文件
        user_session: 用户会话，用于发送反应

    Returns:
        DownloadResult: 下载结果，包含版本号、成功数量和失败数量
    """

    origin_version = await GameResourceDownloader.get_version()
    version_file = CACHE_DIR.joinpath("version")
    local_version = version_file.read_text(encoding="utf-8") if version_file.exists() else None
    if local_version == origin_version and not force:
        logger.info("游戏图片资源已是最新版本")
        return DownloadResult(version=None, success_count=0, failed_count=0)

    if user_session:
        send_reaction(user_session, "processing")
    logger.info(f"检测到新版本 {origin_version}，开始下载游戏资源")
    total_success = 0
    total_failed = 0
    for route in RESOURCE_ROUTES:
        logger.info(f"正在下载: {route}")
        result = await GameResourceDownloader.download_all(
            owner="yuanyan3060",
            repo="ArknightsGameResource",
            route=route,
            save_dir=CACHE_DIR,
            branch="main",
            update=update,
        )
        total_success += result.success_count
        total_failed += result.failed_count
    GameResourceDownloader.update_version_file(origin_version)
    if user_session:
        send_reaction(user_session, "done")
    logger.success(f"游戏资源已更新到版本：{origin_version}")
    return DownloadResult(
        version=origin_version,
        success_count=total_success,
        failed_count=total_failed,
    )
