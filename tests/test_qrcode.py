"""Behavior tests for avatar-backed login QR cards."""

from io import BytesIO
from types import SimpleNamespace

import httpx
import pytest
import qrcode
from PIL import Image, ImageChops


def _png_bytes(size: tuple[int, int] = (128, 128)) -> bytes:
    stream = BytesIO()
    Image.new("RGB", size, (32, 96, 160)).save(stream, "PNG")
    return stream.getvalue()


def _expected_qr(scan_url: str) -> Image.Image:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(scan_url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


@pytest.mark.parametrize(
    ("avatar", "panel_top"),
    [
        (None, 32),
        (Image.new("RGB", (160, 160), (32, 96, 160)), 136),
    ],
)
def test_render_qrcode_card_preserves_qr_pixels(app, avatar, panel_top):
    from nonebot_plugin_skland.commands.bind import _render_qrcode_card

    scan_url = "hypergryph://scan_login?scanId=test-scan-id"
    raw = _render_qrcode_card(scan_url, avatar)
    expected_qr = _expected_qr(scan_url)

    with Image.open(BytesIO(raw)) as image:
        card = image.convert("RGB")

    panel_padding = 24
    panel_size = expected_qr.width + panel_padding * 2
    panel_left = (card.width - panel_size) // 2
    rendered_qr = card.crop(
        (
            panel_left + panel_padding,
            panel_top + panel_padding,
            panel_left + panel_padding + expected_qr.width,
            panel_top + panel_padding + expected_qr.height,
        )
    )

    assert card.width == 640
    assert ImageChops.difference(rendered_qr, expected_qr).getbbox() is None


def test_avatar_url_rejects_unsafe_targets(app):
    from nonebot_plugin_skland.commands.bind import _is_supported_avatar_url

    assert _is_supported_avatar_url("https://cdn.example.com/avatar.png") is True
    assert _is_supported_avatar_url("http://q1.qlogo.cn/avatar.jpg") is True
    assert _is_supported_avatar_url("file:///tmp/avatar.png") is False
    assert _is_supported_avatar_url("http://localhost/avatar.png") is False
    assert _is_supported_avatar_url("http://127.0.0.1/avatar.png") is False
    assert _is_supported_avatar_url("http://user:password@example.com/avatar.png") is False


@pytest.mark.asyncio
async def test_fetch_user_avatar_reads_valid_image(app, mocker):
    import nonebot_plugin_skland.commands.bind as bind

    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, headers={"content-type": "image/png"}, content=_png_bytes())
    )

    def create_client(*args, **kwargs):
        kwargs["transport"] = transport
        return client_type(*args, **kwargs)

    mocker.patch.object(bind.httpx, "AsyncClient", side_effect=create_client)

    avatar = await bind._fetch_user_avatar("https://cdn.example.com/avatar.png")

    assert avatar is not None
    assert avatar.mode == "RGB"
    assert avatar.size == (128, 128)


@pytest.mark.asyncio
async def test_fetch_user_avatar_ignores_non_image(app, mocker):
    import nonebot_plugin_skland.commands.bind as bind

    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, headers={"content-type": "text/plain"}, content=b"not an image")
    )

    def create_client(*args, **kwargs):
        kwargs["transport"] = transport
        return client_type(*args, **kwargs)

    mocker.patch.object(bind.httpx, "AsyncClient", side_effect=create_client)

    assert await bind._fetch_user_avatar("https://cdn.example.com/avatar.png") is None


@pytest.mark.asyncio
async def test_qrcode_handler_marks_group_owner(app, mocker):
    import nonebot_plugin_skland.commands.bind as bind

    avatar = Image.new("RGB", (128, 128), (32, 96, 160))
    fetch_avatar = mocker.patch.object(bind, "_fetch_user_avatar", new=mocker.AsyncMock(return_value=avatar))
    render_card = mocker.patch.object(bind, "_render_qrcode_card", return_value=b"qr-card")
    mocker.patch.object(bind, "send_reaction")
    mocker.patch.object(bind.SklandLoginAPI, "get_scan", new=mocker.AsyncMock(return_value="scan-id"))
    mocker.patch.object(bind.SklandLoginAPI, "get_scan_status", new=mocker.AsyncMock(return_value="scan-code"))
    mocker.patch.object(bind.SklandLoginAPI, "get_token_by_scan_code", new=mocker.AsyncMock(return_value="t" * 24))
    mocker.patch.object(bind.SklandLoginAPI, "get_grant_code", new=mocker.AsyncMock(return_value="grant"))
    mocker.patch.object(
        bind.SklandLoginAPI,
        "get_cred",
        new=mocker.AsyncMock(return_value=SimpleNamespace(cred="cred", token="cred-token", userId="skland-id")),
    )
    get_binding = mocker.patch.object(bind.SklandAPI, "get_binding", new=mocker.AsyncMock(return_value=[]))
    confirm = mocker.patch.object(bind, "_confirm_account_binding", new=mocker.AsyncMock())

    qr_message = SimpleNamespace(recallable=True, recall=mocker.AsyncMock())
    send = mocker.patch.object(bind.UniMessage, "send", new=mocker.AsyncMock(return_value=qr_message))
    mocker.patch.object(bind.UniMessage, "finish", new=mocker.AsyncMock())

    session = SimpleNamespace()
    user_session = SimpleNamespace(
        user_id=1,
        platform_user=SimpleNamespace(avatar="https://cdn.example.com/avatar.png"),
        session=SimpleNamespace(scene=SimpleNamespace(is_private=False)),
    )

    await bind.qrcode_handler(user_session, session)

    fetch_avatar.assert_awaited_once_with("https://cdn.example.com/avatar.png")
    render_card.assert_called_once_with("hypergryph://scan_login?scanId=scan-id", avatar)
    send.assert_awaited_once_with(reply_to=True, at_sender=True)
    qr_message.recall.assert_awaited_once_with(index=0)
    get_binding.assert_awaited_once()
    confirm.assert_awaited_once()
    assert confirm.await_args.kwargs["mode"] == "upsert"
    assert confirm.await_args.kwargs["snapshot"].skland_user_id == "skland-id"
