"""Skland account binding commands."""

import asyncio
import ipaddress
from io import BytesIO
from typing import Literal
from dataclasses import dataclass
from urllib.parse import urlsplit
from datetime import datetime, timedelta

import httpx
import qrcode
from nonebot import logger
from sqlalchemy.exc import IntegrityError
from nonebot_plugin_user import UserSession
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_waiter.unimsg import prompt_until
from nonebot_plugin_alconna import Match, Arparma, MsgTarget, UniMessage
from PIL import Image, ImageOps, ImageDraw, ImageFilter, UnidentifiedImageError

from ..model import SkUser
from ..utils import send_reaction
from ..db_handler import get_accounts
from ..player_data import ark_card_data
from ..api import SklandAPI, SklandLoginAPI
from ..render import render_bound_roles_card
from ..schemas import CRED, BoundRolesPlan, BindingAccountSnapshot
from ..exception import LoginException, RequestException, UnauthorizedException
from ..account import (
    AccountOperationInProgress,
    apply_planned_defaults,
    build_bound_roles_plan,
    exclusive_account_operation,
    reconcile_account_characters,
)

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


async def _fetch_user_avatar(avatar_url: str | None) -> Image.Image | None:
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


def _render_qrcode_card(scan_url: str, avatar: Image.Image | None) -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(scan_url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")

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


@dataclass(frozen=True, slots=True)
class PendingCredential:
    access_token: str | None
    cred: str
    cred_token: str
    skland_user_id: str


@dataclass(frozen=True, slots=True)
class AccountIdentityOverride:
    account_id: int
    original_skland_user_id: str | None
    resolved_skland_user_id: str


@dataclass(frozen=True, slots=True)
class _DetachedAccountCredential:
    account_id: int
    original_skland_user_id: str | None
    access_token: str | None
    cred: str
    cred_token: str


class _ExistingIdentityResolutionError(RuntimeError):
    pass


class _DuplicateAccountIdentityError(RuntimeError):
    pass


async def _resolve_pending_credential(value: str) -> PendingCredential:
    credential = value.strip()
    if len(credential) == 24:
        grant_code = await SklandLoginAPI.get_grant_code(credential, 0)
        cred = await SklandLoginAPI.get_cred(grant_code)
        skland_user_id = cred.userId or await SklandAPI.get_user_ID(cred)
        if not skland_user_id:
            raise RequestException("未能解析森空岛账号身份")
        return PendingCredential(
            access_token=credential,
            cred=cred.cred,
            cred_token=cred.token,
            skland_user_id=skland_user_id,
        )
    if len(credential) == 32:
        cred_token = await SklandLoginAPI.refresh_token(credential)
        cred = CRED(cred=credential, token=cred_token)
        skland_user_id = await SklandAPI.get_user_ID(cred)
        if not skland_user_id:
            raise RequestException("未能解析森空岛账号身份")
        return PendingCredential(
            access_token=None,
            cred=credential,
            cred_token=cred_token,
            skland_user_id=skland_user_id,
        )
    raise ValueError("token 或 cred 错误,请检查格式")


async def _resolve_existing_account_identity(account: _DetachedAccountCredential) -> str:
    cred = CRED(cred=account.cred, token=account.cred_token)
    try:
        return await SklandAPI.get_user_ID(cred)
    except UnauthorizedException:
        refreshed_token = await SklandLoginAPI.refresh_token(account.cred)
        return await SklandAPI.get_user_ID(CRED(cred=account.cred, token=refreshed_token))
    except LoginException:
        if not account.access_token:
            raise
        grant_code = await SklandLoginAPI.get_grant_code(account.access_token, 0)
        refreshed_cred = await SklandLoginAPI.get_cred(grant_code)
        return refreshed_cred.userId or await SklandAPI.get_user_ID(refreshed_cred)


async def _load_detached_accounts(
    owner_id: int,
    session: async_scoped_session,
) -> list[_DetachedAccountCredential]:
    try:
        accounts = await get_accounts(owner_id, session)
        return [
            _DetachedAccountCredential(
                account_id=account.id,
                original_skland_user_id=account.skland_user_id,
                access_token=account.access_token,
                cred=account.cred,
                cred_token=account.cred_token,
            )
            for account in accounts
        ]
    finally:
        await session.rollback()


async def _resolve_account_overrides(
    accounts: list[_DetachedAccountCredential],
    candidate_skland_user_id: str,
) -> tuple[int | None, list[AccountIdentityOverride]]:
    stored_ids = [account.original_skland_user_id for account in accounts if account.original_skland_user_id]
    if len(stored_ids) != len(set(stored_ids)):
        raise _DuplicateAccountIdentityError

    direct = [account.account_id for account in accounts if account.original_skland_user_id == candidate_skland_user_id]
    if direct:
        return direct[0], []

    overrides: list[AccountIdentityOverride] = []
    resolved_ids: set[str] = set()
    target_account_id: int | None = None
    for account in accounts:
        try:
            resolved = await _resolve_existing_account_identity(account)
        except (LoginException, RequestException, UnauthorizedException) as error:
            raise _ExistingIdentityResolutionError from error
        if not resolved or resolved in resolved_ids:
            raise _DuplicateAccountIdentityError
        resolved_ids.add(resolved)
        if resolved == candidate_skland_user_id:
            target_account_id = account.account_id
        if resolved != account.original_skland_user_id:
            overrides.append(
                AccountIdentityOverride(
                    account_id=account.account_id,
                    original_skland_user_id=account.original_skland_user_id,
                    resolved_skland_user_id=resolved,
                )
            )
    return target_account_id, overrides


async def _build_detached_plan(
    owner_id: int,
    session: async_scoped_session,
    **kwargs,
) -> BoundRolesPlan:
    try:
        return await build_bound_roles_plan(owner_id, session, **kwargs)
    finally:
        await session.rollback()


def _card_message(user_session: UserSession, image: bytes, text: str) -> UniMessage:
    message = UniMessage()
    if not user_session.session.scene.is_private:
        message.at(str(user_session.platform_user.id)).text("\n")
    return message.image(raw=image).text(f"\n{text}")


async def _render_plan_card(plan: BoundRolesPlan) -> bytes | None:
    try:
        return await render_bound_roles_card(plan.card)
    except Exception:
        logger.exception("Failed to render the bound-role card")
        return None


async def _send_changed_binding_plan(
    user_session: UserSession,
    plan: BoundRolesPlan,
    text: str,
) -> None:
    image = await _render_plan_card(plan)
    if image is None:
        await UniMessage(text).send(at_sender=True)
        return
    await _card_message(user_session, image, text).send(reply_to=True)


async def _confirm_account_binding(
    *,
    owner_id: int,
    pending: PendingCredential,
    snapshot: BindingAccountSnapshot,
    mode: Literal["add", "update", "upsert"],
    user_session: UserSession,
    session: async_scoped_session,
) -> None:
    detached_accounts = await _load_detached_accounts(owner_id, session)
    expected_identities = [(account.account_id, account.original_skland_user_id) for account in detached_accounts]
    try:
        target_account_id, identity_overrides = await _resolve_account_overrides(
            detached_accounts,
            pending.skland_user_id,
        )
    except _ExistingIdentityResolutionError:
        await UniMessage("现有账号身份校验失败,请先执行 sk char update 或解绑异常账号").send(at_sender=True)
        return
    except _DuplicateAccountIdentityError:
        await UniMessage("检测到重复账号数据,请通过 sk unbind 移除异常项").send(at_sender=True)
        return

    if mode == "add" and target_account_id is not None:
        await UniMessage("该森空岛账号已绑定,请使用 sk bind -u 更新").send(at_sender=True)
        return
    if mode == "update" and target_account_id is None:
        await UniMessage("未找到该森空岛账号,请去掉 -u 后重新绑定").send(at_sender=True)
        return

    override_map = {override.account_id: override.resolved_skland_user_id for override in identity_overrides}
    try:
        confirmed_plan = await _build_detached_plan(
            owner_id,
            session,
            mode="bind_confirmation",
            pending_snapshot=snapshot,
            pending_account_id=target_account_id,
            account_identity_overrides=override_map,
        )
    except ValueError:
        await UniMessage("检测到重复账号数据,请通过 sk unbind 移除异常项").send(at_sender=True)
        return

    image = await _render_plan_card(confirmed_plan)
    if image is None:
        await UniMessage("角色列表渲染失败,未保存账号").send(at_sender=True)
        return

    has_available_roles = any(role.is_available for role in snapshot.roles)
    if target_account_id is None and not has_available_roles:
        await _card_message(
            user_session,
            image,
            "未找到可绑定的明日方舟或终末地角色,未保存账号",
        ).send(reply_to=True)
        return

    response = await prompt_until(
        _card_message(
            user_session,
            image,
            "请核对角色列表,回复「确认」保存账号,回复「取消」放弃(60 秒)",
        ),
        lambda message: message.extract_plain_text().strip() in {"确认", "取消"},
        timeout=60,
        retry=2,
        retry_prompt="仅接受「确认」或「取消」,请重新回复",
        timeout_prompt="确认超时,未保存账号",
        limited_prompt="确认次数已用尽,未保存账号",
    )
    if response is None:
        return
    if response.extract_plain_text().strip() == "取消":
        await UniMessage("已取消绑定,未保存账号").send(at_sender=True)
        return

    current_accounts = await get_accounts(owner_id, session)
    current_identities = [(account.id, account.skland_user_id) for account in current_accounts]
    try:
        latest_plan = await build_bound_roles_plan(
            owner_id,
            session,
            mode="bind_confirmation",
            pending_snapshot=snapshot,
            pending_account_id=target_account_id,
            account_identity_overrides=override_map,
        )
    except ValueError:
        await session.rollback()
        await UniMessage("绑定数据已变化,请重新确认").send(at_sender=True)
        return
    if current_identities != expected_identities or latest_plan != confirmed_plan:
        await session.rollback()
        await _send_changed_binding_plan(user_session, latest_plan, "绑定数据已变化,请重新确认")
        return

    current_by_id = {account.id: account for account in current_accounts}
    try:
        for override in identity_overrides:
            account = current_by_id[override.account_id]
            if account.skland_user_id != override.original_skland_user_id:
                raise ValueError("account identity changed during confirmation")
            account.skland_user_id = override.resolved_skland_user_id

        if target_account_id is None:
            target_account = SkUser(
                owner_id=owner_id,
                access_token=pending.access_token,
                cred=pending.cred,
                cred_token=pending.cred_token,
                skland_user_id=pending.skland_user_id,
            )
            session.add(target_account)
            await session.flush()
        else:
            target_account = current_by_id[target_account_id]
            if pending.access_token is not None:
                target_account.access_token = pending.access_token
            target_account.cred = pending.cred
            target_account.cred_token = pending.cred_token
            target_account.skland_user_id = pending.skland_user_id

        await reconcile_account_characters(target_account, snapshot, session)
        await apply_planned_defaults(owner_id, confirmed_plan.planned_defaults, session)
        invalidated_account_ids = set(override_map) | {target_account.id}
        await session.commit()
    except (IntegrityError, KeyError, ValueError):
        await session.rollback()
        try:
            conflict_plan = await _build_detached_plan(
                owner_id,
                session,
                mode="bind_confirmation",
                pending_snapshot=snapshot,
                pending_account_id=target_account_id,
                account_identity_overrides=override_map,
            )
        except ValueError:
            await UniMessage("绑定数据已变化,请重新确认").send(at_sender=True)
            return
        await _send_changed_binding_plan(user_session, conflict_plan, "绑定数据已变化,请重新确认")
        return

    for account_id in invalidated_account_ids:
        await ark_card_data.invalidate_account(account_id)
    send_reaction(user_session, "done")
    await UniMessage("账号更新成功" if target_account_id is not None else "绑定成功").send(at_sender=True)


async def bind_handler(
    token: Match[str],
    result: Arparma,
    user_session: UserSession,
    msg_target: MsgTarget,
    session: async_scoped_session,
) -> None:
    owner_id = user_session.user_id
    if not msg_target.private:
        send_reaction(user_session, "unmatch")
        await UniMessage("绑定指令只允许在私聊中使用").send(at_sender=True)
        return
    if not token.available:
        send_reaction(user_session, "unmatch")
        await UniMessage("token 或 cred 错误,请检查格式").send(at_sender=True)
        return

    try:
        async with exclusive_account_operation(owner_id):
            try:
                pending = await _resolve_pending_credential(token.result)
                apps = await SklandAPI.get_binding(CRED(cred=pending.cred, token=pending.cred_token))
                snapshot = BindingAccountSnapshot.from_apps(pending.skland_user_id, apps)
            except ValueError as error:
                send_reaction(user_session, "unmatch")
                await UniMessage(str(error)).send(at_sender=True)
                return
            except (LoginException, RequestException, UnauthorizedException) as error:
                send_reaction(user_session, "fail")
                await UniMessage(f"绑定失败,错误信息:{error}").send(at_sender=True)
                return
            await _confirm_account_binding(
                owner_id=owner_id,
                pending=pending,
                snapshot=snapshot,
                mode="update" if result.find("bind.update") else "add",
                user_session=user_session,
                session=session,
            )
    except AccountOperationInProgress:
        await UniMessage("已有账号管理操作进行中").send(at_sender=True)


async def qrcode_handler(
    user_session: UserSession,
    session: async_scoped_session,
) -> None:
    owner_id = user_session.user_id
    try:
        async with exclusive_account_operation(owner_id):
            send_reaction(user_session, "processing")
            try:
                avatar = await _fetch_user_avatar(user_session.platform_user.avatar)
                scan_id = await SklandLoginAPI.get_scan()
                scan_url = f"hypergryph://scan_login?scanId={scan_id}"
                qr_image = _render_qrcode_card(scan_url, avatar)
                message = UniMessage(
                    "请使用森空岛 App 扫描二维码绑定账号\n二维码绑定将由本次命令发起者在角色列表中确认,有效时间约两分钟"
                )
                message += UniMessage.image(raw=qr_image)
                qr_message = await message.send(
                    reply_to=True,
                    at_sender=not user_session.session.scene.is_private,
                )
                end_time = datetime.now() + timedelta(seconds=100)
                scan_code = None
                while datetime.now() < end_time:
                    try:
                        scan_code = await SklandLoginAPI.get_scan_status(scan_id)
                        break
                    except RequestException:
                        pass
                    await asyncio.sleep(2)
                if qr_message.recallable:
                    await qr_message.recall(index=0)
                if not scan_code:
                    send_reaction(user_session, "fail")
                    await UniMessage("二维码超时,请重新获取并扫码").send(at_sender=True)
                    return

                send_reaction(user_session, "received")
                token = await SklandLoginAPI.get_token_by_scan_code(scan_code)
                pending = await _resolve_pending_credential(token)
                apps = await SklandAPI.get_binding(CRED(cred=pending.cred, token=pending.cred_token))
                snapshot = BindingAccountSnapshot.from_apps(pending.skland_user_id, apps)
            except (LoginException, RequestException, UnauthorizedException) as error:
                send_reaction(user_session, "fail")
                await UniMessage(f"绑定失败,错误信息:{error}").send(at_sender=True)
                return

            await _confirm_account_binding(
                owner_id=owner_id,
                pending=pending,
                snapshot=snapshot,
                mode="upsert",
                user_session=user_session,
                session=session,
            )
    except AccountOperationInProgress:
        await UniMessage("已有账号管理操作进行中").send(at_sender=True)


async def unbind_handler(
    user_session: UserSession,
    session: async_scoped_session,
) -> None:
    owner_id = user_session.user_id
    try:
        async with exclusive_account_operation(owner_id):
            selection_plan = await _build_detached_plan(
                owner_id,
                session,
                mode="unbind_selection",
            )
            if not selection_plan.card.accounts:
                send_reaction(user_session, "unmatch")
                await UniMessage("你还没有绑定森空岛账号").send(at_sender=True)
                return
            selection_image = await _render_plan_card(selection_plan)
            if selection_image is None:
                await UniMessage("角色列表渲染失败,未做任何更改").send(at_sender=True)
                return

            valid_indexes = {str(account.index) for account in selection_plan.card.accounts}
            response = await prompt_until(
                _card_message(
                    user_session,
                    selection_image,
                    "请回复账号序号,或回复「全部」「取消」(60 秒)",
                ),
                lambda message: message.extract_plain_text().strip() in valid_indexes | {"全部", "取消"},
                timeout=60,
                retry=2,
                retry_prompt="账号序号无效,请回复卡片中的账号序号、「全部」或「取消」",
                timeout_prompt="解绑选择超时,未做任何更改",
                limited_prompt="账号序号输入次数已用尽,未做任何更改",
            )
            if response is None:
                return
            selection = response.extract_plain_text().strip()
            if selection == "取消":
                await UniMessage("已取消解绑操作").send(at_sender=True)
                return
            if selection == "全部":
                selected_account_ids = {
                    account.account_id for account in selection_plan.card.accounts if account.account_id is not None
                }
            else:
                selected_account_ids = {
                    account.account_id
                    for account in selection_plan.card.accounts
                    if account.index == int(selection) and account.account_id is not None
                }

            try:
                confirmed_unbind_plan = await _build_detached_plan(
                    owner_id,
                    session,
                    mode="unbind_confirmation",
                    pending_unbind_account_ids=selected_account_ids,
                )
            except ValueError:
                await UniMessage("绑定数据已变化,请重新操作").send(at_sender=True)
                return
            confirmation_image = await _render_plan_card(confirmed_unbind_plan)
            if confirmation_image is None:
                await UniMessage("角色列表渲染失败,未做任何更改").send(at_sender=True)
                return

            confirmation_text = (
                "确认解绑全部账号将删除所有角色和抽卡记录,回复「确认」继续(30 秒)"
                if selection == "全部"
                else "确认解绑将删除所选账号的角色和抽卡记录,回复「确认」继续(30 秒)"
            )
            confirmation = await prompt_until(
                _card_message(user_session, confirmation_image, confirmation_text),
                lambda _message: True,
                timeout=30,
                retry=0,
                timeout_prompt="解绑确认超时,未做任何更改",
            )
            if confirmation is None:
                return
            if confirmation.extract_plain_text().strip() != "确认":
                await UniMessage("已取消解绑操作").send(at_sender=True)
                return

            try:
                latest_unbind_plan = await build_bound_roles_plan(
                    owner_id,
                    session,
                    mode="unbind_confirmation",
                    pending_unbind_account_ids=selected_account_ids,
                )
            except ValueError:
                await session.rollback()
                await UniMessage("绑定数据已变化,请重新操作").send(at_sender=True)
                return
            if latest_unbind_plan != confirmed_unbind_plan:
                await session.rollback()
                await _send_changed_binding_plan(
                    user_session,
                    latest_unbind_plan,
                    "绑定数据已变化,请重新操作",
                )
                return

            accounts = await get_accounts(owner_id, session)
            accounts_by_id = {account.id: account for account in accounts}
            if not selected_account_ids.issubset(accounts_by_id):
                await session.rollback()
                await UniMessage("绑定数据已变化,请重新操作").send(at_sender=True)
                return
            for account_id in selected_account_ids:
                await session.delete(accounts_by_id[account_id])
            await session.commit()
            for account_id in selected_account_ids:
                await ark_card_data.invalidate_account(account_id)

            overview = await _build_detached_plan(
                owner_id,
                session,
                mode="overview",
            )
            send_reaction(user_session, "done")
            if not overview.card.accounts:
                await UniMessage("解绑成功,已清除全部绑定数据").send(at_sender=True)
                return
            await _send_changed_binding_plan(user_session, overview, "解绑成功")
    except AccountOperationInProgress:
        await UniMessage("已有账号管理操作进行中").send(at_sender=True)
