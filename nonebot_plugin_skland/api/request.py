import hmac
import json
import hashlib
from typing import Literal
from datetime import datetime
from urllib.parse import urlparse

import httpx
from loguru import logger

from ..schemas import CRED, ArkSignResponse
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
                        raise UnauthorizedException(f"arksign失败：{response.json().get('message')}")
                    elif status == 10002:
                        raise LoginException(f"arksign失败：{response.json().get('message')}")
                    elif status != 0:
                        raise RequestException(f"arksign失败：{response.json().get('message')}")
            except httpx.HTTPError as e:
                raise RequestException(f"获取arksign失败: {e}")
            return ArkSignResponse(**response.json()["data"])
