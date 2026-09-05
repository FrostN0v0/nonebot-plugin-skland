from nonebot_plugin_orm import Model
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy import VARCHAR, Text, BigInteger, ForeignKey, UniqueConstraint


class SkUser(Model):
    __tablename__ = "skland_user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    """Skland account binding ID."""
    owner_id: Mapped[int] = mapped_column(index=True)
    """NoneBot user ID that owns this binding."""
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Skland access token."""
    cred: Mapped[str] = mapped_column(Text)
    """Skland login credential."""
    cred_token: Mapped[str] = mapped_column(Text)
    """Skland login credential token."""
    skland_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Remote Skland user ID."""

    characters: Mapped[list["Character"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (UniqueConstraint("owner_id", "skland_user_id", name="uq_skland_user_owner_account"),)


class Character(Model):
    __tablename__ = "skland_characters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    """Game character ID."""
    account_id: Mapped[int] = mapped_column(ForeignKey("skland_user.id", ondelete="CASCADE"), index=True)
    """Owning Skland account binding ID."""
    uid: Mapped[str] = mapped_column(Text)
    """Top-level binding UID."""
    role_id: Mapped[str] = mapped_column(VARCHAR, comment="Game role ID")
    """Concrete game role ID."""
    app_code: Mapped[str] = mapped_column(Text)
    """Game application code."""
    channel_master_id: Mapped[str] = mapped_column(Text)
    """Game server ID."""
    server_name: Mapped[str] = mapped_column(Text)
    """Game server display name."""
    nickname: Mapped[str] = mapped_column(Text)
    """Character nickname."""
    level: Mapped[int | None] = mapped_column(nullable=True)
    """Character level when exposed by the binding API."""
    is_skland_default: Mapped[bool] = mapped_column(default=False, server_default="0")
    """Remote default marker used only for display and initial selection."""

    account: Mapped[SkUser] = relationship(back_populates="characters")
    gacha_records: Mapped[list["GachaRecord"]] = relationship(
        back_populates="character",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    default_records: Mapped[list["CharacterDefault"]] = relationship(
        back_populates="character",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "app_code",
            "channel_master_id",
            "role_id",
            name="uq_skland_character_account_game_role_server",
        ),
    )


class CharacterDefault(Model):
    __tablename__ = "skland_character_default"

    owner_id: Mapped[int] = mapped_column(primary_key=True)
    app_code: Mapped[str] = mapped_column(Text, primary_key=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("skland_characters.id", ondelete="CASCADE"),
        unique=True,
    )

    character: Mapped[Character] = relationship(back_populates="default_records")


class GachaRecord(Model):
    __tablename__ = "skland_gacha_record"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    """Gacha record ID."""
    character_id: Mapped[int] = mapped_column(
        ForeignKey("skland_characters.id", ondelete="CASCADE"),
        index=True,
    )
    """Owning game character ID."""
    character: Mapped[Character] = relationship(back_populates="gacha_records")
    pool_id: Mapped[str] = mapped_column(Text, index=True)
    """Gacha pool ID."""
    pool_name: Mapped[str] = mapped_column(Text)
    """Gacha pool name."""
    item_type: Mapped[str] = mapped_column(Text, default="char", server_default="char")
    """Item type: char or weapon."""
    char_id: Mapped[str] = mapped_column(Text)
    """Item ID."""
    char_name: Mapped[str] = mapped_column(Text)
    """Item name."""
    rarity: Mapped[int]
    """Item rarity."""
    is_new: Mapped[bool]
    """Whether this was the first acquisition."""
    is_free: Mapped[bool] = mapped_column(default=False, server_default="0")
    """Whether this was a free Endfield character-pool pull."""
    gacha_ts: Mapped[int] = mapped_column(BigInteger, comment="Gacha timestamp")
    pos: Mapped[int]
    """Gacha sequence position."""

    __table_args__ = (UniqueConstraint("character_id", "gacha_ts", "pos", name="uq_skland_gacha_character_ts_pos"),)
