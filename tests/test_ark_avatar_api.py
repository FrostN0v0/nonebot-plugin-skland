import httpx
import pytest

_UID = "synthetic-uid +/&=猫"
_AVATAR_URL = "https://example.com/avatar.png"


@pytest.fixture
def avatar_api(app, mocker):
    from nonebot_plugin_skland.schemas import CRED
    from nonebot_plugin_skland.api.request import SklandAPI

    client_type = httpx.AsyncClient
    cred = CRED(cred="synthetic-cred", token="synthetic-token")

    async def call(respond):
        client = client_type(transport=httpx.MockTransport(respond))
        mocker.patch.object(httpx, "AsyncClient", return_value=client)
        return await SklandAPI.ark_avatar(cred, uid=_UID)

    return call


@pytest.mark.parametrize(("avatar", "expected"), [({"url": _AVATAR_URL}, _AVATAR_URL), (None, ""), ({"url": None}, "")])
async def test_signed_get_reads_plain_json_avatar(avatar_api, avatar, expected):
    url = "https://zonai.skland.com/api/v1/game/assist/user-info?uid=synthetic-uid+%2B%2F%26%3D%E7%8C%AB"

    def respond(request):
        assert request.method == "GET"
        assert str(request.url) == url
        assert request.headers["cred"] == "synthetic-cred"
        assert request.headers["sign"]
        assert "x-transformed" not in request.headers
        return httpx.Response(200, json={"code": 0, "data": {"gameAvatar": avatar}})

    assert await avatar_api(respond) == expected


@pytest.mark.parametrize(
    ("status", "code", "error_type"),
    [(401, 10000, "UnauthorizedException"), (403, 10002, "LoginException"), (200, 7, "RequestException")],
)
async def test_uses_skland_business_errors(avatar_api, status, code, error_type):
    from nonebot_plugin_skland import exception

    with pytest.raises(getattr(exception, error_type), match="森空岛提示"):
        await avatar_api(lambda _: httpx.Response(status, json={"code": code, "message": "森空岛提示"}))


async def test_gateway_error_is_a_request_error(avatar_api):
    from nonebot_plugin_skland.exception import RequestException

    with pytest.raises(RequestException):
        await avatar_api(lambda _: httpx.Response(502, text="Bad Gateway"))
