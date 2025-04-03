from sqlalchemy import Text
from nonebot_plugin_orm import Model
from sqlalchemy.orm import Mapped, mapped_column


class User(Model):
    __tablename__ = "skland_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    """User ID"""
    access_token: Mapped[str] = mapped_column(Text, nullable=True)
    """Skland Access Token"""
    cred: Mapped[str] = mapped_column(Text)
    """Skland Login Credential"""
    cred_token: Mapped[str] = mapped_column(Text)
    """Skland Login Credential Token"""
    user_id: Mapped[str] = mapped_column(Text, nullable=True)
    """Skland User ID"""


class Character(Model):
    __tablename__ = "skland_characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    """Character ID"""
    uid: Mapped[str] = mapped_column(primary_key=True)
    """Character UID"""
    app_code: Mapped[str] = mapped_column(Text)
    """APP Code"""
    channel_master_id: Mapped[str] = mapped_column(Text)
    """Channel Master ID"""
    nickname: Mapped[str] = mapped_column(Text)
    """Character Nickname"""
    isdefault: Mapped[bool] = mapped_column(default=False)
