"""
森空岛 API 接口测试

凭证获取优先级：
1. tests/cred_cache.json（本地持久化缓存）
2. 环境变量 SKLAND_TOKEN（24位 token）或 SKLAND_CRED（32位 cred）
3. 二维码扫码登录（终端打印 + 保存 tests/qrcode.png）

凭证过期时自动刷新并重新持久化。
"""

import os
import re
import json
import asyncio
from io import BytesIO
from pathlib import Path

import httpx
import pytest
import qrcode
from nonebot import logger

TESTS_DIR = Path(__file__).parent
CRED_CACHE_PATH = TESTS_DIR / "cred_cache.json"
QR_IMAGE_PATH = TESTS_DIR / "qrcode.png"


# ==================== 凭证管理 ====================


def _load_cached_cred() -> dict | None:
    """从本地 JSON 文件加载缓存的凭证"""
    if CRED_CACHE_PATH.exists():
        data = json.loads(CRED_CACHE_PATH.read_text(encoding="utf-8"))
        if data.get("cred") and data.get("token"):
            return data
    return None


def _save_cred_cache(cred_dict: dict) -> None:
    """将凭证持久化到本地 JSON 文件"""
    CRED_CACHE_PATH.write_text(json.dumps(cred_dict, ensure_ascii=False, indent=2), encoding="utf-8")


async def _get_cred_by_token(token: str) -> dict:
    """通过 24 位 access_token 获取 CRED"""
    from nonebot_plugin_skland.api import SklandLoginAPI

    grant_code = await SklandLoginAPI.get_grant_code(token, 0)
    cred = await SklandLoginAPI.get_cred(grant_code)
    return {"cred": cred.cred, "token": cred.token, "userId": cred.userId, "access_token": token}


async def _get_cred_by_cred_str(cred_str: str) -> dict:
    """通过 32 位 cred 字符串获取 CRED（刷新 cred_token）"""
    from nonebot_plugin_skland.schemas import CRED
    from nonebot_plugin_skland.api import SklandAPI, SklandLoginAPI

    cred_token = await SklandLoginAPI.refresh_token(cred_str)
    user_id = await SklandAPI.get_user_ID(CRED(cred=cred_str, token=cred_token))
    return {"cred": cred_str, "token": cred_token, "userId": user_id}


async def _get_cred_by_qrcode() -> dict:
    """通过扫码登录获取 CRED，同时在终端打印二维码并保存图片到本地"""
    from nonebot_plugin_skland.api import SklandLoginAPI
    from nonebot_plugin_skland.exception import RequestException

    scan_id = await SklandLoginAPI.get_scan()
    scan_url = f"hypergryph://scan_login?scanId={scan_id}"

    qr = qrcode.QRCode(border=1)
    qr.add_data(scan_url)
    qr.make(fit=True)
    logger.info("\n" + "=" * 50)
    logger.info("请使用森空岛 App 扫描下方二维码登录")
    logger.info("=" * 50)
    qr.print_ascii(invert=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, "PNG")
    QR_IMAGE_PATH.write_bytes(buf.getvalue())
    logger.info(f"二维码图片已保存到: {QR_IMAGE_PATH}")
    logger.info("等待扫码中（最长 120 秒）...")

    scan_code = None
    for _ in range(60):
        try:
            scan_code = await SklandLoginAPI.get_scan_status(scan_id)
            break
        except RequestException:
            pass
        await asyncio.sleep(2)

    if not scan_code:
        pytest.fail("二维码扫码超时，请重新运行测试")

    logger.success("扫码成功，正在获取凭证...")
    token = await SklandLoginAPI.get_token_by_scan_code(scan_code)
    grant_code = await SklandLoginAPI.get_grant_code(token, 0)
    cred = await SklandLoginAPI.get_cred(grant_code)
    return {"cred": cred.cred, "token": cred.token, "userId": cred.userId, "access_token": token}


async def _try_refresh_cred(cached: dict) -> dict:
    """尝试刷新凭证；若成功则更新并返回，若失败则抛出异常"""
    from nonebot_plugin_skland.api import SklandLoginAPI
    from nonebot_plugin_skland.exception import RequestException

    if access_token := cached.get("access_token"):
        try:
            refreshed = await _get_cred_by_token(access_token)
            _save_cred_cache(refreshed)
            logger.success("通过 access_token 刷新凭证成功")
            return refreshed
        except RequestException:
            pass

    try:
        new_token = await SklandLoginAPI.refresh_token(cached["cred"])
        cached["token"] = new_token
        _save_cred_cache(cached)
        logger.success("通过 cred 刷新 cred_token 成功")
        return cached
    except Exception as e:
        raise RuntimeError(f"凭证刷新失败: {e}，请删除 {CRED_CACHE_PATH} 后重新登录") from e


@pytest.fixture(scope="session")
async def cred():
    """
    Session 级凭证 fixture，整个测试会话只获取一次。

    获取优先级：
    1. tests/cred_cache.json
    2. 环境变量 SKLAND_TOKEN (24位) 或 SKLAND_CRED (32位)
    3. 二维码扫码

    获取后自动持久化到 tests/cred_cache.json。
    """
    from nonebot_plugin_skland.schemas import CRED

    # 尝试从缓存加载
    if cached := _load_cached_cred():
        # 验证凭证是否仍然有效
        try:
            from nonebot_plugin_skland.api import SklandAPI

            await SklandAPI.get_binding(CRED(cred=cached["cred"], token=cached["token"], userId=cached.get("userId")))
            logger.success("使用缓存凭证")
            return CRED(cred=cached["cred"], token=cached["token"], userId=cached.get("userId"))
        except Exception:
            logger.warning("缓存凭证已过期，尝试刷新...")
            try:
                cached = await _try_refresh_cred(cached)
                return CRED(cred=cached["cred"], token=cached["token"], userId=cached.get("userId"))
            except RuntimeError:
                logger.warning("刷新失败，回退到其他获取方式...")

    # 尝试从环境变量获取
    cred_dict = None
    if token := os.environ.get("SKLAND_TOKEN"):
        logger.info("通过环境变量 SKLAND_TOKEN 获取凭证...")
        cred_dict = await _get_cred_by_token(token)
    elif cred_str := os.environ.get("SKLAND_CRED"):
        logger.info("通过环境变量 SKLAND_CRED 获取凭证...")
        cred_dict = await _get_cred_by_cred_str(cred_str)

    # 二维码扫码
    if cred_dict is None:
        logger.info("未找到缓存或环境变量，启动二维码扫码登录...")
        cred_dict = await _get_cred_by_qrcode()

    # 持久化
    _save_cred_cache(cred_dict)
    logger.success("凭证已持久化到 tests/cred_cache.json")
    return CRED(cred=cred_dict["cred"], token=cred_dict["token"], userId=cred_dict.get("userId"))


@pytest.fixture(scope="session")
async def binding(cred):
    """获取绑定角色列表，供后续测试复用"""
    from nonebot_plugin_skland.api import SklandAPI

    apps = await SklandAPI.get_binding(cred)
    return apps


# ==================== 签名与 Header 测试 ====================


class TestSignHeader:
    """验证 get_sign_header 生成的请求头格式与签名正确性"""

    async def test_get_header_contains_required_fields(self, cred):
        """返回的 header 应包含 cred、sign、platform、timestamp 等必要字段"""
        from nonebot_plugin_skland.api import SklandAPI

        url = "https://zonai.skland.com/api/v1/game/player/binding"
        headers = await SklandAPI.get_sign_header(cred, url, method="get")

        assert "cred" in headers, "header 缺少 cred 字段"
        assert "sign" in headers, "header 缺少 sign 字段"
        assert "platform" in headers, "header 缺少 platform 字段"
        assert "timestamp" in headers, "header 缺少 timestamp 字段"
        assert "dId" in headers, "header 缺少 dId 字段"
        assert "vName" in headers, "header 缺少 vName 字段"
        assert "User-Agent" in headers, "header 缺少 User-Agent 字段"

    async def test_sign_is_valid_md5_hex(self, cred):
        """sign 字段应为 32 位十六进制字符串（MD5 输出）"""
        from nonebot_plugin_skland.api import SklandAPI

        url = "https://zonai.skland.com/api/v1/game/player/binding"
        headers = await SklandAPI.get_sign_header(cred, url, method="get")

        sign = headers["sign"]
        assert len(sign) == 32, f"sign 长度应为 32，实际为 {len(sign)}"
        assert re.fullmatch(r"[0-9a-f]{32}", sign), f"sign 应为小写十六进制字符串，实际为 {sign}"

    async def test_post_header_with_body(self, cred):
        """POST 请求带 body 时签名应正常生成"""
        from nonebot_plugin_skland.api import SklandAPI

        url = "https://zonai.skland.com/api/v1/game/attendance"
        body = {"uid": "12345678", "gameId": "1"}
        headers = await SklandAPI.get_sign_header(cred, url, method="post", query_body=body)

        assert headers["cred"] == cred.cred
        assert re.fullmatch(r"[0-9a-f]{32}", headers["sign"])

    async def test_get_header_with_query_string(self, cred):
        """GET 请求带 query string 时签名应正确处理"""
        from nonebot_plugin_skland.api import SklandAPI

        url = "https://zonai.skland.com/api/v1/game/player/info?uid=12345678"
        headers = await SklandAPI.get_sign_header(cred, url, method="get")

        assert re.fullmatch(r"[0-9a-f]{32}", headers["sign"])

    async def test_different_urls_produce_different_signs(self, cred):
        """不同 URL 应产生不同的签名"""
        from nonebot_plugin_skland.api import SklandAPI

        url1 = "https://zonai.skland.com/api/v1/game/player/binding"
        url2 = "https://zonai.skland.com/api/v1/game/player/info?uid=12345678"
        h1 = await SklandAPI.get_sign_header(cred, url1, method="get")
        h2 = await SklandAPI.get_sign_header(cred, url2, method="get")

        assert h1["sign"] != h2["sign"], "不同 URL 的签名不应相同"


# ==================== 真实接口测试 ====================


class TestRealAPI:
    """调用真实接口验证返回数据结构"""

    async def test_get_binding(self, cred, binding):
        """获取绑定角色列表"""
        assert isinstance(binding, list), "binding 应为列表"
        assert len(binding) > 0, "绑定角色列表不应为空"
        # 每个元素应有 appCode 和 bindingList 字段
        for app in binding:
            assert hasattr(app, "appCode"), "BindingApp 缺少 appCode"
            assert hasattr(app, "bindingList"), "BindingApp 缺少 bindingList"
        logger.success(f"获取到 {len(binding)} 个游戏的绑定信息")

    async def test_get_user_id(self, cred):
        """获取用户 userId"""
        from nonebot_plugin_skland.api import SklandAPI

        user_id = await SklandAPI.get_user_ID(cred)
        assert isinstance(user_id, str), "userId 应为字符串"
        assert len(user_id) > 0, "userId 不应为空"
        logger.success(f"userId = {user_id}")

    async def test_ark_card(self, cred, binding):
        """获取明日方舟角色卡片（需要已绑定明日方舟角色）"""
        from nonebot_plugin_skland.api import SklandAPI

        ark_apps = [app for app in binding if app.appCode == "arknights"]
        if not ark_apps or not ark_apps[0].bindingList:
            pytest.skip("未绑定明日方舟角色")

        uid = ark_apps[0].bindingList[0].uid
        card = await SklandAPI.ark_card(cred, uid)
        assert card is not None, "返回的卡片数据不应为空"
        logger.success(f"获取到明日方舟角色卡片，uid={uid}")

    async def test_endfield_card(self, cred, binding):
        """获取终末地角色卡片（需要已绑定终末地角色）"""
        from nonebot_plugin_skland.api import SklandAPI
        from nonebot_plugin_skland.model import Character

        ef_apps = [app for app in binding if app.appCode == "endfield"]
        if not ef_apps or not ef_apps[0].bindingList:
            pytest.skip("未绑定终末地角色")

        char_info = ef_apps[0].bindingList[0]
        role = char_info.roles[0] if char_info.roles else None
        if not role:
            pytest.skip("终末地角色无 role 信息")

        # 构造 Character 对象供 endfield_card 使用
        char = Character(
            id=0,
            uid=char_info.uid,
            role_id=role.roleId,
            nickname=role.nickname,
            app_code="endfield",
            channel_master_id=role.serverId,
        )
        card = await SklandAPI.endfield_card(cred, cred.userId, char)
        assert card is not None, "返回的终末地卡片数据不应为空"
        logger.success(f"获取到终末地角色卡片，roleId={role.roleId}")


# ==================== 自定义接口测试模板 ====================


class TestCustomEndpoint:
    """
    自定义接口测试模板。
    如有需测试的接口，请按下方示例，修改接口地址、请求方法、添加请求体等，并添加断言验证返回数据结构。
    如果需要使用 dId，请确保在 get_sign_header 中传入 use_did=True。
    """

    async def test_custom_get_endpoint(self, cred):
        from nonebot_plugin_skland.api import SklandAPI

        url = "https://zonai.skland.com/web/v1/wiki/item/catalog?typeMainId=1&typeSubId=1"
        headers = await SklandAPI.get_sign_header(cred, url, method="get", use_did=True)

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

        data = response.json()
        logger.info(f"响应状态码: {response.status_code}")
        logger.info(f"响应 code: {data.get('code')}")
        logger.info(f"响应数据 keys: {list(data.get('data', {}).keys()) if data.get('data') else 'N/A'}")

        assert response.status_code == 200, f"HTTP 状态码异常: {response.status_code}"
        assert data.get("code", -1) == 0, f"接口返回错误: {data.get('message', data)}"
