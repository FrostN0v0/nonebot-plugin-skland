import httpx

from ..schemas import CRED
from ..exception import RequestException

app_code = "4ca99fa6b56cc2ba"


class SklandLoginAPI:
    _headers = {
        "User-Agent": ("Skland/1.32.1 (com.hypergryph.skland; build:103201004; Android 33; ) Okhttp/4.11.0"),
        "Accept-Encoding": "gzip",
        "Connection": "close",
    }

    @classmethod
    async def get_grant_code(cls, token: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://as.hypergryph.com/user/oauth2/v2/grant",
                json={"appCode": app_code, "token": token, "type": 0},
                headers={**cls._headers},
            )

            if status := response.json().get("status"):
                if status != 0:
                    raise RequestException(f"使用token获得认证代码失败：{response.json().get('msg')}")
            return response.json()["data"]["code"]

    @classmethod
    async def get_cred(cls, grant_code: str) -> CRED:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://zonai.skland.com/api/v1/user/auth/generate_cred_by_code",
                json={"code": grant_code, "kind": 1},
                headers={**cls._headers},
            )
            if status := response.json().get("status"):
                if status != 0:
                    raise RequestException(f"获得cred失败：{response.json().get('messgae')}")
            return CRED(**response.json().get("data"))

    @classmethod
    async def refresh_token(cls, cred: str) -> str:
        async with httpx.AsyncClient() as client:
            refresh_url = "https://zonai.skland.com/api/v1/auth/refresh"
            try:
                response = await client.get(
                    refresh_url,
                    headers={**cls._headers, "cred": cred},
                )
                response.raise_for_status()
                if status := response.json().get("status"):
                    if status != 0:
                        raise RequestException(f"刷新token失败：{response.json().get('message')}")
                token = response.json().get("data").get("token")
                return token
            except (httpx.HTTPStatusError, httpx.ConnectError) as e:
                raise RequestException(f"刷新token失败：{str(e)}")
