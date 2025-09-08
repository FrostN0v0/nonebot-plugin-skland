from nonebot_plugin_orm import Model
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy import VARCHAR, Text, Integer, BigInteger, ForeignKey, UniqueConstraint, ForeignKeyConstraint


class SkUser(Model):
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

    gacha_records: Mapped[list["GachaRecord"]] = relationship("GachaRecord", back_populates="user")


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

    gacha_records: Mapped[list["GachaRecord"]] = relationship("GachaRecord", back_populates="character")


class GachaRecord(Model):
    __tablename__ = "skland_gacha_record"

    id: Mapped[int] = mapped_column(primary_key=True)
    """Gacha Record ID"""
    uid: Mapped[int] = mapped_column(ForeignKey("skland_user.id"), comment="关联的用户ID", index=True)
    """关联的用户ID"""
    char_pk_id: Mapped[int] = mapped_column(Integer, comment="关联角色的复合主键ID部分")
    char_uid: Mapped[str] = mapped_column(VARCHAR, comment="关联的角色UID", index=True)
    """关联的角色UID"""
    user: Mapped["SkUser"] = relationship("SkUser", back_populates="gacha_records")
    """关联的用户"""
    character: Mapped["Character"] = relationship(
        "Character",
        back_populates="gacha_records",
        primaryjoin="and_(GachaRecord.char_pk_id == Character.id, GachaRecord.char_uid == Character.uid)",
    )
    """关联的角色"""
    pool_id: Mapped[str] = mapped_column(Text, index=True)
    """Gacha Pool ID"""
    pool_name: Mapped[str] = mapped_column(Text)
    """Gacha Pool Name"""
    char_id: Mapped[str] = mapped_column(Text)
    """Character ID"""
    char_name: Mapped[str] = mapped_column(Text)
    """Character Name"""
    rarity: Mapped[int]
    """Character Rarity"""
    is_new: Mapped[bool]
    """Is New Character"""
    gacha_ts: Mapped[BigInteger] = mapped_column(BigInteger, comment="Gacha Timestamp")
    """Gacha Timestamp"""
    pos: Mapped[int]
    """Gacha Position"""

    __table_args__ = (
        UniqueConstraint("char_id", "gacha_ts", "pos", name="_character_ts_pos_uc"),
        ForeignKeyConstraint(
            ["char_pk_id", "char_uid"],
            ["skland_characters.id", "skland_characters.uid"],
            name="fk_gacha_record_to_characters",
        ),
    )
