"""Migrate Skland bindings to multi-account ownership.

Migration ID: 6f2c3a9b8d71
Parent migration: a689da19471b
Created: 2026-09-04

"""

from __future__ import annotations

from typing import Any
from collections import defaultdict
from collections.abc import Mapping, Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision: str = "6f2c3a9b8d71"
down_revision: str | Sequence[str] | None = "a689da19471b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_USER_TABLE = "_skland_user_multi"
_NEW_CHARACTER_TABLE = "_skland_characters_multi"
_NEW_DEFAULT_TABLE = "_skland_character_default_multi"
_NEW_GACHA_TABLE = "_skland_gacha_record_multi"

_LEGACY_USER_TABLE = "_skland_user_legacy"
_LEGACY_CHARACTER_TABLE = "_skland_characters_legacy"
_LEGACY_GACHA_TABLE = "_skland_gacha_record_legacy"

_POSTGRES_TEMP_CONSTRAINT_SUFFIX = "__migration_tmp"

_NEW_CONSTRAINT_NAMES: dict[str, tuple[str, ...]] = {
    "skland_user": ("pk_skland_user", "uq_skland_user_owner_account"),
    "skland_characters": (
        "pk_skland_characters",
        "uq_skland_character_account_game_role_server",
    ),
    "skland_character_default": (
        "pk_skland_character_default",
        "uq_skland_character_default_character_id",
    ),
    "skland_gacha_record": (
        "pk_skland_gacha_record",
        "uq_skland_gacha_character_ts_pos",
    ),
}

_LEGACY_CONSTRAINT_NAMES: dict[str, tuple[str, ...]] = {
    "skland_user": ("pk_skland_user",),
    "skland_characters": ("pk_skland_characters",),
    "skland_gacha_record": ("pk_skland_gacha_record", "_app_char_ts_pos_uc"),
}


class _MigrationError(RuntimeError):
    pass


def _reflect(bind: Connection, table_name: str) -> sa.Table:
    return sa.Table(table_name, sa.MetaData(), autoload_with=bind)


def _count(bind: Connection, table: sa.Table) -> int:
    return int(bind.scalar(sa.select(sa.func.count()).select_from(table)) or 0)


def _assert_count(bind: Connection, table: sa.Table, expected: int) -> None:
    actual = _count(bind, table)
    if actual != expected:
        raise _MigrationError(f"row count mismatch for {table.name}: expected {expected}, got {actual}")


def _assert_foreign_keys(bind: Connection) -> None:
    if bind.dialect.name != "sqlite":
        return
    violations = bind.execute(sa.text("PRAGMA foreign_key_check")).all()
    if violations:
        raise _MigrationError(f"foreign key validation failed: {violations!r}")


def _constraint_name(bind: Connection, name: str) -> str:
    if bind.dialect.name == "postgresql":
        return f"{name}{_POSTGRES_TEMP_CONSTRAINT_SUFFIX}"
    return name


def _restore_constraint_names(bind: Connection, constraints: Mapping[str, Sequence[str]]) -> None:
    if bind.dialect.name != "postgresql":
        return

    preparer = bind.dialect.identifier_preparer
    for table_name, names in constraints.items():
        quoted_table_name = preparer.quote(table_name)
        for name in names:
            temporary_name = _constraint_name(bind, name)
            bind.execute(
                sa.text(
                    f"ALTER TABLE {quoted_table_name} "
                    f"RENAME CONSTRAINT {preparer.quote(temporary_name)} TO {preparer.quote(name)}"
                )
            )


def _new_tables(bind: Connection) -> tuple[sa.Table, sa.Table, sa.Table, sa.Table]:
    users = op.create_table(
        _NEW_USER_TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("cred", sa.Text(), nullable=False),
        sa.Column("cred_token", sa.Text(), nullable=False),
        sa.Column("skland_user_id", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=_constraint_name(bind, "pk_skland_user")),
        sa.UniqueConstraint(
            "owner_id",
            "skland_user_id",
            name=_constraint_name(bind, "uq_skland_user_owner_account"),
        ),
        info={"bind_key": "nonebot_plugin_skland"},
    )
    characters = op.create_table(
        _NEW_CHARACTER_TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("uid", sa.Text(), nullable=False),
        sa.Column("role_id", sa.VARCHAR(), nullable=False, comment="Game role ID"),
        sa.Column("app_code", sa.Text(), nullable=False),
        sa.Column("channel_master_id", sa.Text(), nullable=False),
        sa.Column("server_name", sa.Text(), nullable=False),
        sa.Column("nickname", sa.Text(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("is_skland_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            [f"{_NEW_USER_TABLE}.id"],
            name="fk_skland_characters_account_id_skland_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=_constraint_name(bind, "pk_skland_characters")),
        sa.UniqueConstraint(
            "account_id",
            "app_code",
            "channel_master_id",
            "role_id",
            name=_constraint_name(bind, "uq_skland_character_account_game_role_server"),
        ),
        info={"bind_key": "nonebot_plugin_skland"},
    )
    defaults = op.create_table(
        _NEW_DEFAULT_TABLE,
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("app_code", sa.Text(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["character_id"],
            [f"{_NEW_CHARACTER_TABLE}.id"],
            name="fk_skland_character_default_character_id_skland_characters",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "owner_id",
            "app_code",
            name=_constraint_name(bind, "pk_skland_character_default"),
        ),
        sa.UniqueConstraint(
            "character_id",
            name=_constraint_name(bind, "uq_skland_character_default_character_id"),
        ),
        info={"bind_key": "nonebot_plugin_skland"},
    )
    gacha = op.create_table(
        _NEW_GACHA_TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("pool_id", sa.Text(), nullable=False),
        sa.Column("pool_name", sa.Text(), nullable=False),
        sa.Column("item_type", sa.Text(), server_default="char", nullable=False),
        sa.Column("char_id", sa.Text(), nullable=False),
        sa.Column("char_name", sa.Text(), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("is_new", sa.Boolean(), nullable=False),
        sa.Column("is_free", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("gacha_ts", sa.BigInteger(), nullable=False, comment="Gacha timestamp"),
        sa.Column("pos", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["character_id"],
            [f"{_NEW_CHARACTER_TABLE}.id"],
            name="fk_skland_gacha_record_character_id_skland_characters",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=_constraint_name(bind, "pk_skland_gacha_record")),
        sa.UniqueConstraint(
            "character_id",
            "gacha_ts",
            "pos",
            name=_constraint_name(bind, "uq_skland_gacha_character_ts_pos"),
        ),
        info={"bind_key": "nonebot_plugin_skland"},
    )
    return users, characters, defaults, gacha


def _legacy_tables(bind: Connection) -> tuple[sa.Table, sa.Table, sa.Table]:
    users = op.create_table(
        _LEGACY_USER_TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("cred", sa.Text(), nullable=False),
        sa.Column("cred_token", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=_constraint_name(bind, "pk_skland_user")),
        info={"bind_key": "nonebot_plugin_skland"},
    )
    characters = op.create_table(
        _LEGACY_CHARACTER_TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uid", sa.String(), nullable=False),
        sa.Column("app_code", sa.Text(), nullable=False),
        sa.Column("channel_master_id", sa.Text(), nullable=False),
        sa.Column("nickname", sa.Text(), nullable=False),
        sa.Column("isdefault", sa.Boolean(), nullable=False),
        sa.Column("role_id", sa.VARCHAR(), nullable=True, comment="Game role ID"),
        sa.PrimaryKeyConstraint("id", "uid", name=_constraint_name(bind, "pk_skland_characters")),
        info={"bind_key": "nonebot_plugin_skland"},
    )
    gacha = op.create_table(
        _LEGACY_GACHA_TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", sa.Integer(), nullable=False, comment="Associated user ID"),
        sa.Column("char_pk_id", sa.Integer(), nullable=False, comment="Character composite key ID"),
        sa.Column("char_uid", sa.VARCHAR(), nullable=False, comment="Character UID"),
        sa.Column("pool_id", sa.Text(), nullable=False),
        sa.Column("pool_name", sa.Text(), nullable=False),
        sa.Column("char_id", sa.Text(), nullable=False),
        sa.Column("char_name", sa.Text(), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("is_new", sa.Boolean(), nullable=False),
        sa.Column("gacha_ts", sa.BigInteger(), nullable=False, comment="Gacha timestamp"),
        sa.Column("pos", sa.Integer(), nullable=False),
        sa.Column("app_code", sa.Text(), server_default="arknights", nullable=False),
        sa.Column("item_type", sa.Text(), server_default="char", nullable=False),
        sa.Column("is_free", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(
            ["char_pk_id", "char_uid"],
            [f"{_LEGACY_CHARACTER_TABLE}.id", f"{_LEGACY_CHARACTER_TABLE}.uid"],
            name="fk_gacha_record_to_characters",
        ),
        sa.ForeignKeyConstraint(
            ["uid"],
            [f"{_LEGACY_USER_TABLE}.id"],
            name="fk_skland_gacha_record_uid_skland_user",
        ),
        sa.PrimaryKeyConstraint("id", name=_constraint_name(bind, "pk_skland_gacha_record")),
        sa.UniqueConstraint(
            "char_uid",
            "app_code",
            "gacha_ts",
            "pos",
            name=_constraint_name(bind, "_app_char_ts_pos_uc"),
        ),
        info={"bind_key": "nonebot_plugin_skland"},
    )
    return users, characters, gacha


def _copy_upgrade_data(
    bind: Connection,
    old_users: sa.Table,
    old_characters: sa.Table,
    old_gacha: sa.Table,
    new_users: sa.Table,
    new_characters: sa.Table,
    new_defaults: sa.Table,
    new_gacha: sa.Table,
) -> None:
    user_rows = list(bind.execute(sa.select(old_users).order_by(old_users.c.id)).mappings())
    character_rows = list(
        bind.execute(sa.select(old_characters).order_by(old_characters.c.id, old_characters.c.uid)).mappings()
    )
    old_user_ids = {int(row["id"]) for row in user_rows}
    character_by_old_key: dict[tuple[int, str], Mapping[str, Any]] = {}
    normalized_role_keys: set[tuple[int, str, str, str]] = set()

    for row in character_rows:
        old_account_id = int(row["id"])
        uid = str(row["uid"])
        if old_account_id not in old_user_ids:
            raise _MigrationError(f"orphan character: {(old_account_id, uid)!r}")
        old_key = (old_account_id, uid)
        character_by_old_key[old_key] = row
        role_id = str(row["role_id"] or uid)
        role_key = (old_account_id, str(row["app_code"]), str(row["channel_master_id"]), role_id)
        if role_key in normalized_role_keys:
            raise _MigrationError(f"normalized character identity conflict: {role_key!r}")
        normalized_role_keys.add(role_key)

    collapsed_gacha_keys: set[tuple[tuple[int, str], int, int]] = set()
    for row in bind.execute(sa.select(old_gacha).order_by(old_gacha.c.id)).mappings():
        user_id = int(row["uid"])
        character_account_id = int(row["char_pk_id"])
        character_key = (character_account_id, str(row["char_uid"]))
        if user_id not in old_user_ids:
            raise _MigrationError(f"orphan gacha account: {user_id}")
        if user_id != character_account_id:
            raise _MigrationError(f"gacha ownership mismatch: user {user_id}, character account {character_account_id}")
        character = character_by_old_key.get(character_key)
        if character is None:
            raise _MigrationError(f"orphan gacha character: {character_key!r}")
        if str(row["app_code"]) != str(character["app_code"]):
            raise _MigrationError(
                f"gacha game mismatch for {character_key!r}: {row['app_code']!r} != {character['app_code']!r}"
            )
        collapsed_key = (character_key, int(row["gacha_ts"]), int(row["pos"]))
        if collapsed_key in collapsed_gacha_keys:
            raise _MigrationError(f"collapsed gacha identity conflict: {collapsed_key!r}")
        collapsed_gacha_keys.add(collapsed_key)

    account_id_map: dict[int, int] = {}
    for row in user_rows:
        old_id = int(row["id"])
        result = bind.execute(
            new_users.insert().values(
                owner_id=old_id,
                access_token=row["access_token"],
                cred=row["cred"],
                cred_token=row["cred_token"],
                skland_user_id=row["user_id"],
            )
        )
        account_id_map[old_id] = int(result.inserted_primary_key[0])

    character_id_map: dict[tuple[int, str], int] = {}
    default_groups: dict[tuple[int, str], list[tuple[int, bool]]] = defaultdict(list)
    for row in character_rows:
        old_account_id = int(row["id"])
        uid = str(row["uid"])
        result = bind.execute(
            new_characters.insert().values(
                account_id=account_id_map[old_account_id],
                uid=uid,
                role_id=str(row["role_id"] or uid),
                app_code=str(row["app_code"]),
                channel_master_id=str(row["channel_master_id"]),
                server_name=str(row["channel_master_id"]),
                nickname=str(row["nickname"]),
                level=None,
                is_skland_default=False,
            )
        )
        character_id = int(result.inserted_primary_key[0])
        old_key = (old_account_id, uid)
        character_id_map[old_key] = character_id
        default_groups[(old_account_id, str(row["app_code"]))].append((character_id, bool(row["isdefault"])))

    for (owner_id, app_code), candidates in default_groups.items():
        explicit = [character_id for character_id, is_default in candidates if is_default]
        character_id: int | None = None
        if len(explicit) == 1:
            character_id = explicit[0]
        elif not explicit and len(candidates) == 1:
            character_id = candidates[0][0]
        if character_id is not None:
            bind.execute(
                new_defaults.insert().values(
                    owner_id=owner_id,
                    app_code=app_code,
                    character_id=character_id,
                )
            )

    for row in bind.execute(sa.select(old_gacha).order_by(old_gacha.c.id)).mappings():
        character_id = character_id_map[(int(row["char_pk_id"]), str(row["char_uid"]))]
        bind.execute(
            new_gacha.insert().values(
                character_id=character_id,
                pool_id=row["pool_id"],
                pool_name=row["pool_name"],
                item_type=row["item_type"],
                char_id=row["char_id"],
                char_name=row["char_name"],
                rarity=row["rarity"],
                is_new=row["is_new"],
                is_free=row["is_free"],
                gacha_ts=row["gacha_ts"],
                pos=row["pos"],
            )
        )

    _assert_count(bind, new_users, len(user_rows))
    _assert_count(bind, new_characters, len(character_rows))
    _assert_count(bind, new_gacha, _count(bind, old_gacha))


def _copy_downgrade_data(
    bind: Connection,
    users: sa.Table,
    characters: sa.Table,
    defaults: sa.Table,
    gacha: sa.Table,
    legacy_users: sa.Table,
    legacy_characters: sa.Table,
    legacy_gacha: sa.Table,
) -> None:
    user_rows = list(bind.execute(sa.select(users).order_by(users.c.id)).mappings())
    character_rows = list(bind.execute(sa.select(characters).order_by(characters.c.id)).mappings())
    default_rows = list(bind.execute(sa.select(defaults)).mappings())

    accounts_by_owner: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    account_by_id: dict[int, Mapping[str, Any]] = {}
    for row in user_rows:
        account_id = int(row["id"])
        owner_id = int(row["owner_id"])
        accounts_by_owner[owner_id].append(row)
        account_by_id[account_id] = row
    if any(len(accounts) > 1 for accounts in accounts_by_owner.values()):
        raise RuntimeError("multi-account data cannot be represented by the legacy schema")

    character_by_id: dict[int, Mapping[str, Any]] = {}
    legacy_character_keys: set[tuple[int, str]] = set()
    for row in character_rows:
        account_id = int(row["account_id"])
        account = account_by_id.get(account_id)
        if account is None:
            raise _MigrationError(f"orphan character account: {account_id}")
        owner_id = int(account["owner_id"])
        key = (owner_id, str(row["uid"]))
        if key in legacy_character_keys:
            raise RuntimeError("multi-account data cannot be represented by the legacy schema")
        legacy_character_keys.add(key)
        character_by_id[int(row["id"])] = row

    default_character_ids: set[int] = set()
    for row in default_rows:
        character_id = int(row["character_id"])
        character = character_by_id.get(character_id)
        if character is None:
            raise _MigrationError(f"orphan default character: {character_id}")
        account = account_by_id[int(character["account_id"])]
        if int(row["owner_id"]) != int(account["owner_id"]) or str(row["app_code"]) != str(character["app_code"]):
            raise _MigrationError(f"default ownership mismatch: {character_id}")
        default_character_ids.add(character_id)

    collapsed_gacha_keys: set[tuple[str, str, int, int]] = set()
    for row in bind.execute(sa.select(gacha).order_by(gacha.c.id)).mappings():
        character = character_by_id.get(int(row["character_id"]))
        if character is None:
            raise _MigrationError(f"orphan gacha character: {row['character_id']}")
        key = (
            str(character["uid"]),
            str(character["app_code"]),
            int(row["gacha_ts"]),
            int(row["pos"]),
        )
        if key in collapsed_gacha_keys:
            raise RuntimeError("multi-account data cannot be represented by the legacy schema")
        collapsed_gacha_keys.add(key)

    for row in user_rows:
        bind.execute(
            legacy_users.insert().values(
                id=int(row["owner_id"]),
                access_token=row["access_token"],
                cred=row["cred"],
                cred_token=row["cred_token"],
                user_id=row["skland_user_id"],
            )
        )

    for row in character_rows:
        account = account_by_id[int(row["account_id"])]
        bind.execute(
            legacy_characters.insert().values(
                id=int(account["owner_id"]),
                uid=str(row["uid"]),
                app_code=row["app_code"],
                channel_master_id=row["channel_master_id"],
                nickname=row["nickname"],
                isdefault=int(row["id"]) in default_character_ids,
                role_id=row["role_id"],
            )
        )

    for row in bind.execute(sa.select(gacha).order_by(gacha.c.id)).mappings():
        character = character_by_id[int(row["character_id"])]
        account = account_by_id[int(character["account_id"])]
        owner_id = int(account["owner_id"])
        bind.execute(
            legacy_gacha.insert().values(
                uid=owner_id,
                char_pk_id=owner_id,
                char_uid=str(character["uid"]),
                pool_id=row["pool_id"],
                pool_name=row["pool_name"],
                char_id=row["char_id"],
                char_name=row["char_name"],
                rarity=row["rarity"],
                is_new=row["is_new"],
                gacha_ts=row["gacha_ts"],
                pos=row["pos"],
                app_code=character["app_code"],
                item_type=row["item_type"],
                is_free=row["is_free"],
            )
        )

    _assert_count(bind, legacy_users, len(user_rows))
    _assert_count(bind, legacy_characters, len(character_rows))
    _assert_count(bind, legacy_gacha, _count(bind, gacha))


def upgrade(name: str = "") -> None:
    if name:
        return

    bind = op.get_bind()
    old_users = _reflect(bind, "skland_user")
    old_characters = _reflect(bind, "skland_characters")
    old_gacha = _reflect(bind, "skland_gacha_record")
    new_users, new_characters, new_defaults, new_gacha = _new_tables(bind)

    _copy_upgrade_data(
        bind,
        old_users,
        old_characters,
        old_gacha,
        new_users,
        new_characters,
        new_defaults,
        new_gacha,
    )

    op.drop_table("skland_gacha_record")
    op.drop_table("skland_characters")
    op.drop_table("skland_user")
    op.rename_table(_NEW_USER_TABLE, "skland_user")
    op.rename_table(_NEW_CHARACTER_TABLE, "skland_characters")
    op.rename_table(_NEW_DEFAULT_TABLE, "skland_character_default")
    op.rename_table(_NEW_GACHA_TABLE, "skland_gacha_record")
    _restore_constraint_names(bind, _NEW_CONSTRAINT_NAMES)

    op.create_index("ix_skland_user_owner_id", "skland_user", ["owner_id"], unique=False)
    op.create_index("ix_skland_characters_account_id", "skland_characters", ["account_id"], unique=False)
    op.create_index(
        "ix_skland_gacha_record_character_id",
        "skland_gacha_record",
        ["character_id"],
        unique=False,
    )
    op.create_index("ix_skland_gacha_record_pool_id", "skland_gacha_record", ["pool_id"], unique=False)

    _assert_foreign_keys(bind)


def downgrade(name: str = "") -> None:
    if name:
        return

    bind = op.get_bind()
    users = _reflect(bind, "skland_user")
    characters = _reflect(bind, "skland_characters")
    defaults = _reflect(bind, "skland_character_default")
    gacha = _reflect(bind, "skland_gacha_record")
    legacy_users, legacy_characters, legacy_gacha = _legacy_tables(bind)

    _copy_downgrade_data(
        bind,
        users,
        characters,
        defaults,
        gacha,
        legacy_users,
        legacy_characters,
        legacy_gacha,
    )

    op.drop_table("skland_character_default")
    op.drop_table("skland_gacha_record")
    op.drop_table("skland_characters")
    op.drop_table("skland_user")
    op.rename_table(_LEGACY_USER_TABLE, "skland_user")
    op.rename_table(_LEGACY_CHARACTER_TABLE, "skland_characters")
    op.rename_table(_LEGACY_GACHA_TABLE, "skland_gacha_record")
    _restore_constraint_names(bind, _LEGACY_CONSTRAINT_NAMES)

    op.create_index("ix_skland_gacha_record_app_code", "skland_gacha_record", ["app_code"], unique=False)
    op.create_index("ix_skland_gacha_record_char_uid", "skland_gacha_record", ["char_uid"], unique=False)
    op.create_index("ix_skland_gacha_record_pool_id", "skland_gacha_record", ["pool_id"], unique=False)
    op.create_index("ix_skland_gacha_record_uid", "skland_gacha_record", ["uid"], unique=False)

    _assert_foreign_keys(bind)
