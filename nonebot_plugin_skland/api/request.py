import hmac
import json
import hashlib
from typing import Literal
from datetime import datetime
from urllib.parse import urlparse

import httpx

from nonebot_plugin_skland.schemas.cred import CRED

from ..exception import RequestException

base_url = "https://zonai.skland.com/api/v1/game/"


class SklandAPI:
    _headers = {
        "User-Agent": (
            "Skland/1.32.1 (com.hypergryph.skland; build:103201004; Android 33; ) "
            "Okhttp/4.11.0"
        ),
        "Accept-Encoding": "gzip",
        "Connection": "close",
    }

    _header_for_sign = {"platform": "", "timestamp": "", "dId": "", "vName": ""}

    @classmethod
    async def get_binding(cls, cred: CRED) -> list:
        """获取绑定的角色"""
        binding_url = f"{base_url}player/binding"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    binding_url,
                    headers=await cls.get_sign_header(cred, binding_url, method="get"),
                )
                if status := response.json().get("status"):
                    if status != 0:
                        raise RequestException(
                            f"获取绑定角色失败：{response.json().get('msg')}"
                        )
                return response.json()["data"]["list"]
            except httpx.HTTPError as e:
                raise RequestException(f"获取绑定角色失败: {e}")

    @classmethod
    async def get_sign_header(
        cls,
        cred: CRED,
        url: str,
        method: Literal["get", "post"],
        query_body: str | None = None,
    ) -> dict:
        """获取带sign请求头"""
        parsed_url = urlparse(url)
        timestamp = int(datetime.now().timestamp())
        header_ca = {**cls._header_for_sign, "timestamp": str(timestamp)}
        if method == "get":
            query_params = parsed_url.query
        elif query_body:
            query_params = query_body
        secret = (
            f"{parsed_url.path}{query_params}{timestamp}"
            f"{json.dumps(header_ca, separators=(',', ':'))}"
        )
        signature = await cls.generate_signature(cred.token, secret)
        return {"cred": cred.cred, **cls._headers, **header_ca, "sign": signature}

    @classmethod
    async def generate_signature(cls, token: str, secret: str) -> str:
        """生成签名"""
        hex_secret = hmac.new(
            token.encode("utf-8"), secret.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return hashlib.md5(hex_secret.encode("utf-8")).hexdigest()
