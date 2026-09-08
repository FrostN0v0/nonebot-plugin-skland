"""Gacha history retrieval, grouping, and Heybox record conversion."""

import asyncio
import itertools
from typing import overload
from collections import defaultdict
from collections.abc import Sequence

import httpx
from nonebot_plugin_orm import async_scoped_session

from ..exception import RequestException
from ..data_source import gacha_table_data
from ..model import Character, GachaRecord
from ..api import SklandAPI, SklandLoginAPI
from ..db_handler import get_character_gacha_records
from ..schemas import (
    GachaCate,
    GachaPool,
    GachaPull,
    GachaGroup,
    EfGachaInfo,
    EfGachaPull,
    EfGachaGroup,
    EfCharGachaInfo,
    EfGachaPoolInfo,
    EndfieldPoolType,
    EfWeaponGachaInfo,
    GroupedGachaRecord,
    EfGroupedGachaRecord,
    EndfieldCharPoolType,
    EndfieldWeaponPoolType,
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
    async with httpx.AsyncClient() as client:
        page = await SklandAPI.get_gacha_history(char.uid, role_token, access_token, ak_cookie, cate.id, client=client)
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
                char.uid,
                role_token,
                access_token,
                ak_cookie,
                cate.id,
                gachaTs=page.next_ts,
                pos=page.next_pos,
                client=client,
            )


@overload
async def get_all_ef_gacha_records(
    server_id: str,
    pool_type: EndfieldCharPoolType,
    role_token: str,
    concurrency: int = 8,
) -> Sequence[EfCharGachaInfo]: ...
@overload
async def get_all_ef_gacha_records(
    server_id: str,
    pool_type: EndfieldWeaponPoolType,
    role_token: str,
    concurrency: int = 8,
) -> Sequence[EfWeaponGachaInfo]: ...


async def get_all_ef_gacha_records(
    server_id: str,
    pool_type: EndfieldPoolType,
    role_token: str,
    concurrency: int = 8,
) -> Sequence[EfGachaInfo]:
    """获取指定卡池类型下的所有终末地抽卡记录。

    自动处理分页，并发请求数据直到获取全部记录。

    Args:
        server_id: Endfield server ID.
        pool_type: Character or weapon pool category, including joint pools.
        role_token: 角色令牌。
        concurrency: 并发请求数量，默认为 8。

    Returns:
        Sequence[EfGachaInfo]: 抽卡记录列表。
    """
    if concurrency <= 0:
        raise ValueError("concurrency must be greater than 0")

    first_page = await SklandAPI.get_ef_gacha_history(pool_type, server_id, role_token)
    if not first_page.gacha_list:
        return []
    if not first_page.hasMore:
        return first_page.gacha_list

    page_size = len(first_page.gacha_list)  # normally 5
    last_seq = first_page.gacha_list[-1].seq_id_int  # shared between workers
    last_seq_lock = asyncio.Lock()

    # the worker fn
    async def fetch_page() -> list[EfGachaInfo]:
        nonlocal last_seq
        records: list[EfGachaInfo] = []
        while True:
            async with last_seq_lock:
                seq_id, last_seq = last_seq, last_seq - page_size
            if seq_id <= 0:
                break
            seq_end = seq_id - page_size
            page = await SklandAPI.get_ef_gacha_history(pool_type, server_id, role_token, str(seq_id), client)
            gacha_infos = [i for i in page.gacha_list if seq_end <= i.seq_id_int < seq_id]
            records.extend(gacha_infos)
            if not page.hasMore:
                break
        return records

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(fetch_page() for _ in range(concurrency)))

    # sort by seq_id descending
    return sorted(itertools.chain(first_page.gacha_list, *results), key=lambda x: x.seq_id_int, reverse=True)


async def sync_ef_gacha_records(
    session: async_scoped_session,
    *,
    character_id: int,
    uid: str,
    server_id: str,
    access_token: str,
) -> tuple[EfGroupedGachaRecord, int]:
    """Fetch complete categories and commit role-owned history before presentation."""
    grant_code = await SklandLoginAPI.get_grant_code(access_token, 1)
    role_token = await SklandLoginAPI.get_role_token_by_uid(uid, grant_code)
    fetched: list[EfGachaInfo] = []
    for pool_type in (
        EndfieldPoolType.STANDARD,
        EndfieldPoolType.SPECIAL,
        EndfieldPoolType.BEGINNER,
        EndfieldPoolType.JOINT,
        EndfieldPoolType.WEAPON,
    ):
        fetched.extend(await get_all_ef_gacha_records(server_id, pool_type, role_token))

    # No database writes occur until every category has been fetched successfully.
    existing = await get_character_gacha_records(character_id, session)
    seen = {(record.gacha_ts, record.pos) for record in existing}
    added: list[GachaRecord] = []
    for item in fetched:
        identity = (item.gacha_ts_sec, item.seq_id_int)
        if identity in seen:
            continue
        seen.add(identity)
        added.append(
            GachaRecord(
                character_id=character_id,
                item_type=item.item_type,
                pool_id=item.poolId,
                pool_name=item.poolName,
                char_id=item.item_id,
                char_name=item.item_name,
                rarity=item.rarity,
                is_new=item.isNew,
                is_free=item.is_free_pull,
                gacha_ts=identity[0],
                pos=identity[1],
            )
        )

    # Build detached statistics while ORM records are still available.
    grouped = group_ef_gacha_records(existing + added)
    session.add_all(added)
    await session.commit()
    return grouped, len(added)


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


def _infer_pool_category(pool_id: str) -> str:
    """根据 pool_id 推导卡池类别"""
    pid = pool_id.lower()
    if pid.startswith("joint"):
        return "joint"
    if pid.startswith("special"):
        return "special"
    if pid.startswith("wepon") or pid.startswith("weapon"):
        return "weapon"
    if pid == "beginner":
        return "beginner"
    return "standard"


def group_ef_gacha_records(records: list[GachaRecord]) -> EfGroupedGachaRecord:
    """将终末地抽卡记录按卡池分组，并根据 pool_id 分类"""
    temp_grouped_records = defaultdict(lambda: defaultdict(list))
    for record in records:
        temp_grouped_records[record.pool_id][record.gacha_ts].append(record)

    beginner_pools: list[EfGachaPoolInfo] = []
    standard_pools: list[EfGachaPoolInfo] = []
    special_pools: list[EfGachaPoolInfo] = []
    joint_pools: list[EfGachaPoolInfo] = []
    weapon_pools: list[EfGachaPoolInfo] = []

    for pool_id, ts_dict in temp_grouped_records.items():
        gacha_groups: list[EfGachaGroup] = [
            EfGachaGroup(
                gacha_ts=gacha_ts,
                pulls=[
                    EfGachaPull(
                        pool_name=p.pool_name,
                        item_id=p.char_id,
                        item_name=p.char_name,
                        item_type=p.item_type,
                        rarity=p.rarity,
                        is_new=p.is_new,
                        is_free=p.is_free,
                        seq_id=p.pos,
                    )
                    for p in pulls
                ],
            )
            for gacha_ts, pulls in ts_dict.items()
        ]
        first_record = next(iter(next(iter(ts_dict.values()))))
        pool_type = first_record.item_type if first_record.item_type else "char"
        pool_info = EfGachaPoolInfo(
            pool_id=pool_id,
            pool_name=gacha_groups[0].pulls[0].pool_name,
            pool_type=pool_type,
            records=gacha_groups,
        )
        category = _infer_pool_category(pool_id)
        if category == "beginner":
            beginner_pools.append(pool_info)
        elif category == "special":
            special_pools.append(pool_info)
        elif category == "joint":
            joint_pools.append(pool_info)
        elif category == "weapon":
            weapon_pools.append(pool_info)
        else:
            standard_pools.append(pool_info)

    return EfGroupedGachaRecord(
        beginner_pools=beginner_pools,
        standard_pools=standard_pools,
        special_pools=special_pools,
        joint_pools=joint_pools,
        weapon_pools=weapon_pools,
    )


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


def heybox_data_to_record(data: dict, character_id: int) -> list[GachaRecord]:
    """Convert Heybox export data into role-owned gacha records."""
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
                    character_id=character_id,
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
