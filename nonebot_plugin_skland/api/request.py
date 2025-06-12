import hmac
import json
import hashlib
from typing import Literal
from datetime import datetime
from urllib.parse import urlparse

import httpx
from nonebot import logger

from ..schemas import CRED, ArkCard, RogueData, ArkSignResponse
from ..exception import LoginException, RequestException, UnauthorizedException

base_url = "https://zonai.skland.com/api/v1"


class SklandAPI:
    _headers = {
        "User-Agent": ("Skland/1.32.1 (com.hypergryph.skland; build:103201004; Android 33; ) Okhttp/4.11.0"),
        "Accept-Encoding": "gzip",
        "Connection": "close",
    }

    _header_for_sign = {"platform": "", "timestamp": "", "dId": "", "vName": ""}

    @classmethod
    async def get_binding(cls, cred: CRED) -> list:
        """获取绑定的角色"""
        binding_url = f"{base_url}/game/player/binding"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    binding_url,
                    headers=cls.get_sign_header(cred, binding_url, method="get"),
                )
                if status := response.json().get("code"):
                    if status == 10000:
                        raise UnauthorizedException(f"获取绑定角色失败：{response.json().get('message')}")
                    elif status == 10002:
                        raise LoginException(f"获取绑定角色失败：{response.json().get('message')}")
                    if status != 0:
                        raise RequestException(f"获取绑定角色失败：{response.json().get('message')}")
                return response.json()["data"]["list"]
            except httpx.HTTPError as e:
                raise RequestException(f"获取绑定角色失败: {e}")

    @classmethod
    def get_sign_header(
        cls,
        cred: CRED,
        url: str,
        method: Literal["get", "post"],
        query_body: dict | None = None,
    ) -> dict:
        """获取带sign请求头"""
        timestamp = int(datetime.now().timestamp()) - 1
        header_ca = {**cls._header_for_sign, "timestamp": str(timestamp)}
        parsed_url = urlparse(url)
        query_params = json.dumps(query_body) if method == "post" else parsed_url.query
        header_ca_str = json.dumps(
            {**cls._header_for_sign, "timestamp": str(timestamp)},
            separators=(",", ":"),
        )
        secret = f"{parsed_url.path}{query_params}{timestamp}{header_ca_str}"
        hex_secret = hmac.new(cred.token.encode("utf-8"), secret.encode("utf-8"), hashlib.sha256).hexdigest()
        signature = hashlib.md5(hex_secret.encode("utf-8")).hexdigest()
        return {"cred": cred.cred, **cls._headers, "sign": signature, **header_ca}

    @classmethod
    async def ark_sign(cls, cred: CRED, uid: str, channel_master_id: str) -> ArkSignResponse:
        """进行明日方舟签到"""
        body = {"uid": uid, "gameId": channel_master_id}
        json_body = json.dumps(body, ensure_ascii=False, separators=(", ", ": "), allow_nan=False)
        sign_url = f"{base_url}/game/attendance"
        headers = cls.get_sign_header(
            cred,
            sign_url,
            method="post",
            query_body=body,
        )
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    sign_url,
                    headers={**headers, "Content-Type": "application/json"},
                    content=json_body,
                )
                logger.debug(f"签到回复：{response.json()}")
                if status := response.json().get("code"):
                    if status == 10000:
                        raise UnauthorizedException(f"角色 {uid} 签到失败：{response.json().get('message')}")
                    elif status == 10002:
                        raise LoginException(f"角色 {uid} 签到失败：{response.json().get('message')}")
                    elif status != 0:
                        raise RequestException(f"角色 {uid} 签到失败：{response.json().get('message')}")
            except httpx.HTTPError as e:
                raise RequestException(f"角色 {uid} 签到失败: {e}")
            return ArkSignResponse(**response.json()["data"])

    @classmethod
    async def get_user_ID(cls, cred: CRED) -> str:
        uid_url = f"{base_url}/user/teenager"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    uid_url,
                    headers=cls.get_sign_header(cred, uid_url, method="get"),
                )
                if status := response.json().get("code"):
                    if status == 10000:
                        raise UnauthorizedException(f"获取账号 userId 失败：{response.json().get('message')}")
                    elif status == 10002:
                        raise LoginException(f"获取账号 userId 失败：{response.json().get('message')}")
                    if status != 0:
                        raise RequestException(f"获取账号 userId 失败：{response.json().get('message')}")
                return response.json()["data"]["teenager"]["userId"]
            except httpx.HTTPError as e:
                raise RequestException(f"获取账号 userId 失败: {e}")

    @classmethod
    async def ark_card(cls, cred: CRED, uid: str) -> ArkCard:
        """获取明日方舟角色信息"""
        game_info_url = f"{base_url}/game/player/info?uid={uid}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    game_info_url,
                    headers=cls.get_sign_header(cred, game_info_url, method="get"),
                )
                if status := response.json().get("code"):
                    if status == 10000:
                        raise UnauthorizedException(f"获取账号 game_info 失败：{response.json().get('message')}")
                    elif status == 10002:
                        raise LoginException(f"获取账号 game_info 失败：{response.json().get('message')}")
                    if status != 0:
                        raise RequestException(f"获取账号 game_info 失败：{response.json().get('message')}")
                return ArkCard(**response.json()["data"])
            except httpx.HTTPError as e:
                raise RequestException(f"获取账号 userId 失败: {e}")

    @classmethod
    async def get_rogue(cls, cred: CRED, uid: str, topic_id: str) -> RogueData:
        """获取肉鸽数据"""
        rogue_url = f"{base_url}/game/arknights/rogue?uid={uid}&targetUserId={cred.userId}&topicId={topic_id}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    rogue_url,
                    headers=cls.get_sign_header(cred, rogue_url, method="get"),
                )
                if status := response.json().get("code"):
                    if status == 10000:
                        raise UnauthorizedException(f"获取肉鸽数据失败：{response.json().get('message')}")
                    elif status == 10002:
                        raise LoginException(f"获取肉鸽数据失败：{response.json().get('message')}")
                    if status != 0:
                        raise RequestException(f"获取肉鸽数据失败：{response.json().get('message')}")
                return RogueData(**response.json()["data"])
            except httpx.HTTPError as e:
                raise RequestException(f"获取肉鸽数据失败: {e}") from e
