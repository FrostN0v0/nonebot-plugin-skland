"""Behavioral coverage for bounded credential refresh and failure propagation."""

import httpx
import pytest


@pytest.mark.parametrize(
    ("failures", "expected_trace", "final_error"),
    [
        ([], ["request"], None),
        (["login"], ["request", "grant", "cred", "request"], None),
        (["unauthorized"], ["request", "token", "request"], None),
        (["unauthorized", "login"], ["request", "token", "request", "grant", "cred", "request"], None),
        (["request"], ["request"], "request"),
        (["login", "unauthorized"], ["request", "grant", "cred", "request"], "unauthorized"),
        (["login", "login"], ["request", "grant", "cred", "request"], "login"),
        (["unauthorized", "unauthorized"], ["request", "token", "request"], "unauthorized"),
        (["unauthorized", "request"], ["request", "token", "request"], "request"),
        (
            ["unauthorized", "login", "login"],
            ["request", "token", "request", "grant", "cred", "request"],
            "login",
        ),
    ],
)
@pytest.mark.asyncio
async def test_refresh_credentials_obeys_retry_budget(app, mocker, failures, expected_trace, final_error):
    from nonebot_plugin_skland.schemas import CRED
    from nonebot_plugin_skland.api import SklandLoginAPI
    from nonebot_plugin_skland.services.auth import CredentialState, refresh_credentials
    from nonebot_plugin_skland.exception import LoginException, RequestException, UnauthorizedException

    errors = {"login": LoginException, "request": RequestException, "unauthorized": UnauthorizedException}
    trace = []
    pending = iter(failures)
    state = CredentialState("access", "old-cred", "old-token")
    result = object()

    async def grant(access_token, app_code):
        trace.append("grant")
        assert access_token == "access"
        assert app_code == 0
        return "grant-code"

    async def cred(grant_code):
        trace.append("cred")
        assert grant_code == "grant-code"
        return CRED(cred="new-cred", token="new-token")

    async def token(credential):
        trace.append("token")
        assert credential == "old-cred"
        return "refreshed-token"

    mocker.patch.object(SklandLoginAPI, "get_grant_code", new=grant)
    mocker.patch.object(SklandLoginAPI, "get_cred", new=cred)
    mocker.patch.object(SklandLoginAPI, "refresh_token", new=token)

    @refresh_credentials
    async def request(user):
        trace.append("request")
        failure = next(pending, None)
        if failure is not None:
            raise errors[failure](failure)
        if "cred" in trace:
            assert (user.cred, user.cred_token) == ("new-cred", "new-token")
        elif "token" in trace:
            assert user.cred_token == "refreshed-token"
        return result

    if final_error is None:
        assert await request(state) is result
    else:
        with pytest.raises(errors[final_error], match=final_error):
            await request(state)
    assert trace == expected_trace


@pytest.mark.parametrize("initial_error", ["login", "unauthorized"])
@pytest.mark.asyncio
async def test_missing_access_token_stops_before_grant_request(app, mocker, initial_error):
    from nonebot_plugin_skland.api import SklandLoginAPI
    from nonebot_plugin_skland.exception import LoginException, UnauthorizedException
    from nonebot_plugin_skland.services.auth import CredentialState, refresh_credentials

    state = CredentialState(None, "cred", "token")
    grant = mocker.patch.object(SklandLoginAPI, "get_grant_code", new=mocker.AsyncMock())
    mocker.patch.object(SklandLoginAPI, "refresh_token", new=mocker.AsyncMock(return_value="refreshed-token"))
    calls = 0

    @refresh_credentials
    async def request(_user):
        nonlocal calls
        calls += 1
        if initial_error == "unauthorized" and calls == 1:
            raise UnauthorizedException("expired token")
        raise LoginException("expired credential")

    with pytest.raises(LoginException):
        await request(state)
    grant.assert_not_awaited()
    assert calls == (2 if initial_error == "unauthorized" else 1)


@pytest.mark.parametrize("refresh_stage", ["token", "grant", "cred"])
@pytest.mark.parametrize("error_name", ["LoginException", "UnauthorizedException", "RequestException"])
@pytest.mark.asyncio
async def test_refresh_failures_propagate_without_another_refresh(app, mocker, refresh_stage, error_name):
    from nonebot_plugin_skland import exception
    from nonebot_plugin_skland.api import SklandLoginAPI
    from nonebot_plugin_skland.services.auth import CredentialState, refresh_credentials

    state = CredentialState("access", "cred", "token")
    failure = getattr(exception, error_name)("refresh failed")
    trace = []

    async def refresh_token(_cred):
        trace.append("token")
        raise failure

    async def get_grant_code(_access, _app):
        trace.append("grant")
        if refresh_stage == "grant":
            raise failure
        return "grant"

    async def get_cred(_grant):
        trace.append("cred")
        raise failure

    mocker.patch.object(SklandLoginAPI, "refresh_token", new=refresh_token)
    mocker.patch.object(SklandLoginAPI, "get_grant_code", new=get_grant_code)
    mocker.patch.object(SklandLoginAPI, "get_cred", new=get_cred)

    @refresh_credentials
    async def request(_user):
        trace.append("request")
        error = exception.UnauthorizedException if refresh_stage == "token" else exception.LoginException
        raise error("expired")

    with pytest.raises(type(failure)) as raised:
        await request(state)
    assert raised.value is failure
    assert trace == (
        ["request", "token"]
        if refresh_stage == "token"
        else ["request", "grant"] + (["cred"] if refresh_stage == "cred" else [])
    )


@pytest.mark.parametrize(
    ("code", "expected_trace", "expected_credentials"),
    [
        (10000, ["request", "token", "request"], ("old-cred", "refreshed-token")),
        (10002, ["request", "grant", "cred", "request"], ("new-cred", "new-token")),
        (99999, ["request"], ("old-cred", "old-token")),
    ],
)
@pytest.mark.asyncio
async def test_api_error_codes_select_the_correct_credential_refresh(
    app, mocker, code, expected_trace, expected_credentials
):
    from nonebot_plugin_skland.schemas import CRED
    from nonebot_plugin_skland.api import SklandAPI
    from nonebot_plugin_skland.exception import RequestException
    from nonebot_plugin_skland.services.auth import CredentialState, refresh_credentials

    state = CredentialState("access", "old-cred", "old-token")
    trace = []
    responses = iter(
        [
            {"code": code, "message": "upstream rejected", "data": None},
            {"code": 0, "data": {"teenager": {"userId": "remote-user"}}},
        ]
    )

    def respond(request):
        if request.url.path == "/api/v1/user/teenager":
            trace.append("request")
            return httpx.Response(200, json=next(responses))
        if request.url.path == "/api/v1/auth/refresh":
            trace.append("token")
            return httpx.Response(200, json={"status": 0, "data": {"token": "refreshed-token"}})
        if request.url.path == "/user/oauth2/v2/grant":
            trace.append("grant")
            return httpx.Response(200, json={"status": 0, "data": {"code": "grant-code"}})
        if request.url.path == "/api/v1/user/auth/generate_cred_by_code":
            trace.append("cred")
            return httpx.Response(200, json={"status": 0, "data": {"cred": "new-cred", "token": "new-token"}})
        raise AssertionError(f"Unexpected request: {request.url.path}")

    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    mocker.patch.object(httpx, "AsyncClient", side_effect=lambda **kwargs: client_type(transport=transport, **kwargs))

    @refresh_credentials
    async def fetch_user_id(credentials):
        return await SklandAPI.get_user_ID(CRED(cred=credentials.cred, token=credentials.cred_token))

    if code == 99999:
        with pytest.raises(RequestException):
            await fetch_user_id(state)
    else:
        assert await fetch_user_id(state) == "remote-user"
    assert trace == expected_trace
    assert (state.cred, state.cred_token) == expected_credentials
