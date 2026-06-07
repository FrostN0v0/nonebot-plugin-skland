import httpx

from ..schemas import CRED
from ..exception import RequestException

skland_app_code = "4ca99fa6b56cc2ba"
web_app_code = "be36d44aa36bfb5b"


class SklandLoginAPI:
    _headers = {
        "User-Agent": ("Skland/1.32.1 (com.hypergryph.skland; build:103201004; Android 33; ) Okhttp/4.11.0"),
        "Accept-Encoding": "gzip",
        "Connection": "close",
    }

    @classmethod
    async def get_grant_code(cls, token: str, grant_type: int) -> str:
        """
        获取认证代码或token。

        Args:
            token (str): 用户token
            grant_type (int): 授权类型。0 返回森空岛认证代码(code)，1 返回官网通行证token。

        Returns:
            str: grant_type 为 0 时返回森空岛认证代码(code)，grant_type 为 1 时返回官网通行证 token。
        """
        async with httpx.AsyncClient() as client:
            code = skland_app_code if grant_type == 0 else web_app_code
            response = await client.post(
                "https://as.hypergryph.com/user/oauth2/v2/grant",
                json={"appCode": code, "token": token, "type": grant_type},
                headers={**cls._headers},
            )
            if status := response.json().get("status"):
                if status != 0:
                    raise RequestException(f"使用token获得认证代码失败：{response.json().get('msg')}")
            return response.json()["data"]["code"] if grant_type == 0 else response.json()["data"]["token"]

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
            except httpx.HTTPError as e:
                raise RequestException(f"刷新token失败：{str(e)}")

    @classmethod
    async def get_scan(cls) -> str:
        async with httpx.AsyncClient() as client:
            get_scan_url = "https://as.hypergryph.com/general/v1/gen_scan/login"
            response = await client.post(
                get_scan_url,
                json={"appCode": skland_app_code},
            )
            if status := response.json().get("status"):
                if status != 0:
                    raise RequestException(f"获取登录二维码失败：{response.json().get('msg')}")
            return response.json()["data"]["scanId"]

    @classmethod
    async def get_scan_status(cls, scan_id: str) -> str:
        async with httpx.AsyncClient() as client:
            get_scan_status_url = "https://as.hypergryph.com/general/v1/scan_status"
            response = await client.get(
                get_scan_status_url,
                params={"scanId": scan_id},
            )
            if status := response.json().get("status"):
                if status != 0:
                    raise RequestException(f"获取二维码 scanCode 失败：{response.json().get('msg')}")
            return response.json()["data"]["scanCode"]

    @classmethod
    async def get_token_by_scan_code(cls, scan_code: str) -> str:
        async with httpx.AsyncClient() as client:
            get_token_by_scan_code_url = "https://as.hypergryph.com/user/auth/v1/token_by_scan_code"
            response = await client.post(
                get_token_by_scan_code_url,
                json={"scanCode": scan_code},
            )
            if status := response.json().get("status"):
                if status != 0:
                    raise RequestException(f"获取token失败：{response.json().get('msg')}")
            return response.json()["data"]["token"]

    @classmethod
    async def get_role_token_by_uid(cls, uid: str, grant_code: str) -> str:
        """获取role_token"""
        async with httpx.AsyncClient() as client:
            get_role_token_url = "https://binding-api-account-prod.hypergryph.com/account/binding/v1/u8_token_by_uid"
            response = await client.post(
                get_role_token_url, json={"uid": uid, "token": grant_code}, headers={"content-type": "application/json"}
            )
            if status := response.json().get("status"):
                if status != 0:
                    raise RequestException(f"获取role token失败：{response.json().get('msg')}")
            return response.json()["data"]["token"]

    @classmethod
    async def get_ak_cookie(cls, role_token: str) -> str:
        """获取官网cookie"""
        async with httpx.AsyncClient() as client:
            get_cookie_url = "https://ak.hypergryph.com/user/api/role/login"
            response = await client.post(
                get_cookie_url,
                headers={"content-type": "application/json", "accept": "application/json"},
                json={"token": role_token},
            )
            if status := response.json().get("status"):
                if status != 0:
                    raise RequestException(f"获取cookie失败：{response.json().get('msg')}")
            if not (cookie := response.cookies.get("ak-user-center")):
                raise RequestException("获取cookie失败：未能获取到 ak-user-center cookie")
            else:
                return cookie
