"""Credential refresh policy shared by interactive and background requests."""

from __future__ import annotations

from functools import wraps
from dataclasses import dataclass
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, TypeVar, ParamSpec, Concatenate

from nonebot import logger

from ..api import SklandLoginAPI
from ..exception import LoginException, UnauthorizedException

if TYPE_CHECKING:
    from ..model import SkUser


@dataclass
class CredentialState:
    """Mutable credentials detached from an ORM account."""

    access_token: str | None
    cred: str
    cred_token: str


P = ParamSpec("P")
R = TypeVar("R")
C = TypeVar("C", bound="SkUser | CredentialState")


async def _refresh_access_credentials(user: SkUser | CredentialState) -> None:
    if not user.access_token:
        raise LoginException("cred失效且账号未保存token")
    grant_code = await SklandLoginAPI.get_grant_code(user.access_token, 0)
    new_cred = await SklandLoginAPI.get_cred(grant_code)
    user.cred, user.cred_token = new_cred.cred, new_cred.token
    logger.info("Refreshed credentials using the saved access token")


def refresh_credentials(
    func: Callable[Concatenate[C, P], Coroutine[None, None, R]],
) -> Callable[Concatenate[C, P], Coroutine[None, None, R]]:
    """Retry expired credentials without replaying request or refresh failures."""

    @wraps(func)
    async def wrapper(user: C, *args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(user, *args, **kwargs)
        except LoginException:
            await _refresh_access_credentials(user)
            return await func(user, *args, **kwargs)
        except UnauthorizedException:
            user.cred_token = await SklandLoginAPI.refresh_token(user.cred)
            logger.info("Refreshed the credential token")
            try:
                return await func(user, *args, **kwargs)
            except LoginException:
                await _refresh_access_credentials(user)
                return await func(user, *args, **kwargs)

    return wrapper
