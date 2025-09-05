from collections import defaultdict

import httpx
from nonebot import logger
from pydantic import AnyUrl as Url
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_orm import async_scoped_session

from .db_handler import delete_characters
from .api import SklandAPI, SklandLoginAPI
from .model import SkUser, Character, GachaRecord
from .config import RES_DIR, CustomSource, config, gacha_table_data
from .exception import LoginException, RequestException, UnauthorizedException
from .schemas import (
    CRED,
    GachaCate,
    GachaPool,
    GachaPull,
    GachaGroup,
    ArkSignResult,
    GroupedGachaRecord,
)


async def get_characters_and_bind(user: SkUser, session: async_scoped_session):
    await delete_characters(user, session)

    cred = CRED(cred=user.cred, token=user.cred_token)
    binding_app_list = await SklandAPI.get_binding(cred)
    for app in binding_app_list:
        for character in app["bindingList"]:
            character_model = Character(
                id=user.id,
                uid=character["uid"],
                nickname=character["nickName"],
                app_code=app["appCode"],
                channel_master_id=character["channelMasterId"],
                isdefault=character["isDefault"],
            )
            if len(app["bindingList"]) == 1:
                character_model.isdefault = True
            session.add(character_model)
    await session.commit()


def refresh_access_token_if_needed(func):
    """装饰器：如果 access_token 失效，刷新后重试"""

    async def wrapper(user: SkUser, *args, **kwargs):
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


def refresh_cred_token_if_needed(func):
    """装饰器：如果 cred_token 失效，刷新后重试"""

    async def wrapper(user: SkUser, *args, **kwargs):
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


def refresh_cred_token_with_error_return(func):
    """装饰器：如果 cred_token 失效，刷新后重试"""

    async def wrapper(user: SkUser, *args, **kwargs):
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


def refresh_access_token_with_error_return(func):
    async def wrapper(user: SkUser, *args, **kwargs):
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
