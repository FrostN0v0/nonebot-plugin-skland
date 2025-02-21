from dataclasses import dataclass


@dataclass
class CRED:
    cred: str
    """登录凭证"""
    token: str
    """登录凭证对应的token"""
    userId: str
    """用户ID"""
