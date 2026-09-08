"""Avatar fetching and pixel-preserving login QR cards."""

import ipaddress
from io import BytesIO
from urllib.parse import urlsplit

import httpx
import qrcode
from qrcode.image.pil import PilImage
from qrcode.constants import ERROR_CORRECT_M
from PIL import Image, ImageOps, ImageDraw, ImageFilter, UnidentifiedImageError

_AVATAR_MAX_BYTES = 2 * 1024 * 1024
_AVATAR_MAX_PIXELS = 4_000_000


def _is_supported_avatar_url(avatar_url: str) -> bool:
    try:
        parsed = urlsplit(avatar_url)
    except ValueError:
        return False
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return True
    return address.is_global


async def fetch_user_avatar(avatar_url: str | None) -> Image.Image | None:
    if not avatar_url or not _is_supported_avatar_url(avatar_url):
        return None
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
            async with client.stream("GET", avatar_url) as response:
                if not 200 <= response.status_code < 300:
                    return None
                content_type = response.headers.get("content-type", "").partition(";")[0].strip().lower()
                if not content_type.startswith("image/"):
                    return None
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > _AVATAR_MAX_BYTES:
                    return None
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > _AVATAR_MAX_BYTES:
                        return None
        with Image.open(BytesIO(body)) as image:
            if image.width * image.height > _AVATAR_MAX_PIXELS:
                return None
            return ImageOps.exif_transpose(image).convert("RGB")
    except (httpx.HTTPError, OSError, UnidentifiedImageError, ValueError):
        return None


def render_qrcode_card(scan_url: str, avatar: Image.Image | None) -> bytes:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(scan_url)
    qr.make(fit=True)
    qr_image = qr.make_image(image_factory=PilImage, fill_color="black", back_color="white").get_image().convert("RGB")

    panel_padding = 24
    panel_size = qr_image.width + panel_padding * 2
    card_width = max(640, panel_size + 64)
    panel_top = 136 if avatar else 32
    card_height = panel_top + panel_size + 32

    if avatar:
        card = ImageOps.fit(avatar, (card_width, card_height), Image.Resampling.LANCZOS)
        card = card.filter(ImageFilter.GaussianBlur(24)).convert("RGBA")
    else:
        card = Image.new("RGBA", (card_width, card_height), (31, 38, 51, 255))
    card.alpha_composite(Image.new("RGBA", card.size, (5, 10, 18, 118)))

    panel_left = (card_width - panel_size) // 2
    panel_box = (
        panel_left,
        panel_top,
        panel_left + panel_size,
        panel_top + panel_size,
    )
    shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (panel_box[0] + 6, panel_box[1] + 10, panel_box[2] + 6, panel_box[3] + 10),
        radius=28,
        fill=(0, 0, 0, 90),
    )
    card.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(12)))
    ImageDraw.Draw(card).rounded_rectangle(panel_box, radius=28, fill=(255, 255, 255, 255))
    card.paste(qr_image, (panel_left + panel_padding, panel_top + panel_padding))

    if avatar:
        badge_size = 88
        badge_left = (card_width - badge_size) // 2
        badge_top = 24
        draw = ImageDraw.Draw(card)
        draw.ellipse(
            (badge_left - 5, badge_top - 5, badge_left + badge_size + 5, badge_top + badge_size + 5),
            fill=(255, 255, 255, 255),
        )
        badge = ImageOps.fit(avatar, (badge_size, badge_size), Image.Resampling.LANCZOS)
        badge_mask = Image.new("L", (badge_size, badge_size), 0)
        ImageDraw.Draw(badge_mask).ellipse((0, 0, badge_size - 1, badge_size - 1), fill=255)
        card.paste(badge, (badge_left, badge_top), badge_mask)

    result_stream = BytesIO()
    card.convert("RGB").save(result_stream, "PNG", optimize=True)
    return result_stream.getvalue()
