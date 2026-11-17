import httpx
import pytest


def _envelope(value):
    return {"code": 0, "data": value}


@pytest.fixture
def garrison_api(app, mocker):
    from nonebot_plugin_skland.schemas import CRED
    from nonebot_plugin_skland.api.request import SklandAPI

    client_type = httpx.AsyncClient
    cred = CRED(cred="synthetic-cred", token="synthetic-token")

    def install(respond):
        transport = httpx.MockTransport(respond)
        mocker.patch.object(
            httpx, "AsyncClient", side_effect=lambda **kwargs: client_type(transport=transport, **kwargs)
        )

    async def call(endpoint, *, activity_id="synthetic-season"):
        if endpoint == "info":
            return await SklandAPI.ark_garrison(cred, uid="synthetic-uid", activity_id=activity_id)
        return await SklandAPI.ark_garrison_resources(cred, activity_id=activity_id)

    return install, call


@pytest.mark.parametrize("endpoint", ["info", "resource"])
@pytest.mark.asyncio
async def test_signed_json_requests_use_scalar_identity(garrison_api, endpoint):
    install, call = garrison_api
    wire = (
        {"history": {"records": [], "favourRecords": []}, "gameUserInfo": {"name": "合成博士"}}
        if endpoint == "info"
        else {"resources": [{"versionInfo": {"activityId": "synthetic-season", "versionId": "test-version"}}]}
    )

    def respond(request):
        assert request.url.path == f"/api/ms/game/arknights/garrison/{endpoint}"
        assert request.url.params["activityId"] == "synthetic-season"
        assert request.url.params.get("uid") == ("synthetic-uid" if endpoint == "info" else None)
        assert "x-transformed" not in request.headers
        assert request.headers["cred"] == "synthetic-cred"
        assert request.headers["sign"]
        return httpx.Response(200, json=_envelope(wire))

    install(respond)
    result = await call(endpoint)
    if endpoint == "info":
        assert result.gameUserInfo.name == "合成博士"
        assert result.history.records == []
    else:
        assert result.current_activity_id == "synthetic-season"


@pytest.mark.asyncio
async def test_resource_omits_activity_query_for_official_current_season(garrison_api):
    install, call = garrison_api

    def respond(request):
        assert "activityId" not in request.url.params
        assert "x-transformed" not in request.headers
        return httpx.Response(
            200, json=_envelope({"resources": [{"versionInfo": {"activityId": "current-test-season"}}]})
        )

    install(respond)
    resources = await call("resource", activity_id=None)
    assert resources.current_activity_id == "current-test-season"


@pytest.mark.parametrize("endpoint", ["info", "resource"])
@pytest.mark.parametrize(
    "failure",
    [
        "outer-json",
        "outer-unicode",
        "outer-array",
        "data-array",
        "data-null",
        "data-missing",
        "model",
        "http",
        "network",
    ],
)
@pytest.mark.asyncio
async def test_malformed_or_failed_responses_are_sanitized(garrison_api, endpoint, failure):
    from nonebot_plugin_skland.exception import RequestException

    install, call = garrison_api

    def respond(request):
        marker = "sensitive-marker"
        if failure == "network":
            raise httpx.ConnectError(f"https://private.test/{marker}", request=request)
        if failure == "http":
            return httpx.Response(503, json={"code": 0, "data": marker})
        if failure == "outer-json":
            return httpx.Response(200, text=marker)
        if failure == "outer-unicode":
            return httpx.Response(200, content=b"\xff")
        if failure == "outer-array":
            return httpx.Response(200, json=[])
        if failure == "data-array":
            return httpx.Response(200, json={"code": 0, "data": []})
        if failure == "data-null":
            return httpx.Response(200, json={"code": 0, "data": None})
        if failure == "data-missing":
            return httpx.Response(200, json={"code": 0})
        return httpx.Response(200, json=_envelope({"history": marker, "resources": marker}))

    install(respond)
    with pytest.raises(RequestException) as exc:
        await call(endpoint)
    message = str(exc.value)
    assert "失败" in message
    assert "sensitive-marker" not in message
    assert "https://" not in message
    assert "synthetic-uid" not in message


@pytest.mark.parametrize("endpoint", ["info", "resource"])
@pytest.mark.parametrize(
    ("code", "error_name"), [(10000, "UnauthorizedException"), (10002, "LoginException"), (7, "RequestException")]
)
@pytest.mark.asyncio
async def test_authentication_codes_take_priority_over_http_status_and_data_validation(
    garrison_api, endpoint, code, error_name
):
    from nonebot_plugin_skland import exception

    install, call = garrison_api

    def respond(request):
        return httpx.Response(400, json={"code": code, "message": "合成业务错误", "data": "sensitive-marker"})

    install(respond)
    with pytest.raises(getattr(exception, error_name), match="合成业务错误"):
        await call(endpoint)
