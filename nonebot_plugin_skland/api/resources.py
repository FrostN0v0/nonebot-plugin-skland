"""Public Endfield resource requests without player credentials."""

import hmac
import json
import hashlib
from time import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from .dId import get_dId
from ..exception import RequestException

WIKI_ORIGIN = "https://zonai.skland.com"
WEAPON_CATALOG_URL = f"{WIKI_ORIGIN}/web/v1/wiki/item/catalog?typeMainId=1&typeSubId=2"


async def get_endfield_weapon_catalog(client: httpx.AsyncClient) -> dict[str, Any]:
    device_id = await get_dId()
    visitor_headers = {"dId": device_id, "platform": "3", "vName": "1.0.0", "Referer": "https://wiki.skland.com/"}
    refreshed = await client.get(f"{WIKI_ORIGIN}/web/v1/auth/refresh", headers=visitor_headers, follow_redirects=False)
    refreshed.raise_for_status()
    payload = refreshed.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    token = data.get("token") if isinstance(data, dict) else None
    if not isinstance(payload, dict) or payload.get("code") != 0 or not isinstance(token, str) or not token:
        raise RequestException("获取终末地武器目录失败：游客认证失败")

    # Wiki issues a short-lived visitor signing token; no saved account is involved.
    fields = {"platform": "3", "timestamp": str(int(time())), "dId": device_id, "vName": "1.0.0"}
    parsed = urlsplit(WEAPON_CATALOG_URL)
    message = parsed.path + parsed.query + fields["timestamp"] + json.dumps(fields, separators=(",", ":"))
    digest = hmac.new(token.encode(), message.encode(), hashlib.sha256).hexdigest()
    response = await client.get(
        WEAPON_CATALOG_URL,
        headers={**visitor_headers, **fields, "sign": hashlib.md5(digest.encode()).hexdigest()},
        follow_redirects=False,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("code") != 0 or not isinstance(payload.get("data"), dict):
        raise RequestException("获取终末地武器目录失败：官方目录不可用")
    return payload["data"]
