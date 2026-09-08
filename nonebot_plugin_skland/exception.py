from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.exception import NoneBotException

if TYPE_CHECKING:
    from .schemas import BoundRolesPlan


class SklandException(NoneBotException):
    """Base error for Skland API and resource requests."""


class RequestException(SklandException):
    """请求错误"""


class UnauthorizedException(SklandException):
    """登录授权错误"""


class LoginException(SklandException):
    """登录错误"""


class AccountOperationInProgress(RuntimeError):
    """Another operation owns this user's account-management scope."""


class AccountIdentityResolutionError(RuntimeError):
    """An existing account's remote identity could not be resolved."""


class DuplicateAccountIdentityError(RuntimeError):
    """Projected account identities are not unique."""


class BindingStateChangedError(RuntimeError):
    """Account state no longer matches the confirmed binding plan."""

    def __init__(self, plan: BoundRolesPlan | None = None) -> None:
        super().__init__("account data changed during confirmation")
        self.plan = plan


class SignCacheFormatError(ValueError):
    """The persisted cache predates role-owned sign entries."""
