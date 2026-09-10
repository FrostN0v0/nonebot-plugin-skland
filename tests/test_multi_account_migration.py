import sys
import importlib.util
from io import StringIO
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.migration import MigrationContext


def _load_migration():
    path = Path("nonebot_plugin_skland/migrations/6f2c3a9b8d71_multi_account_binding.py")
    spec = importlib.util.spec_from_file_location("test_multi_account_migration_module", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _create_legacy_schema(connection: sa.Connection):
    metadata = sa.MetaData()
    users = sa.Table(
        "skland_user",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("access_token", sa.Text, nullable=True),
        sa.Column("cred", sa.Text, nullable=False),
        sa.Column("cred_token", sa.Text, nullable=False),
        sa.Column("user_id", sa.Text, nullable=True),
    )
    characters = sa.Table(
        "skland_characters",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("uid", sa.String, primary_key=True),
        sa.Column("app_code", sa.Text, nullable=False),
        sa.Column("channel_master_id", sa.Text, nullable=False),
        sa.Column("nickname", sa.Text, nullable=False),
        sa.Column("isdefault", sa.Boolean, nullable=False),
        sa.Column("role_id", sa.String, nullable=True),
    )
    gacha = sa.Table(
        "skland_gacha_record",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("uid", sa.Integer, sa.ForeignKey("skland_user.id"), nullable=False),
        sa.Column("char_pk_id", sa.Integer, nullable=False),
        sa.Column("char_uid", sa.String, nullable=False),
        sa.Column("pool_id", sa.Text, nullable=False),
        sa.Column("pool_name", sa.Text, nullable=False),
        sa.Column("char_id", sa.Text, nullable=False),
        sa.Column("char_name", sa.Text, nullable=False),
        sa.Column("rarity", sa.Integer, nullable=False),
        sa.Column("is_new", sa.Boolean, nullable=False),
        sa.Column("gacha_ts", sa.BigInteger, nullable=False),
        sa.Column("pos", sa.Integer, nullable=False),
        sa.Column("app_code", sa.Text, nullable=False),
        sa.Column("item_type", sa.Text, nullable=False),
        sa.Column("is_free", sa.Boolean, nullable=False),
        sa.ForeignKeyConstraint(
            ["char_pk_id", "char_uid"],
            ["skland_characters.id", "skland_characters.uid"],
        ),
        sa.UniqueConstraint("char_uid", "app_code", "gacha_ts", "pos", name="_app_char_ts_pos_uc"),
    )
    metadata.create_all(connection)
    return users, characters, gacha


def _run(connection: sa.Connection, function) -> None:
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        function()


@pytest.mark.parametrize(
    ("factory_name", "constraint_names_name"),
    [
        ("_new_tables", "_NEW_CONSTRAINT_NAMES"),
        ("_legacy_tables", "_LEGACY_CONSTRAINT_NAMES"),
    ],
)
def test_postgresql_table_swap_uses_temporary_constraint_names(factory_name, constraint_names_name):
    migration = _load_migration()
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )

    with Operations.context(context):
        bind = migration.op.get_bind()
        getattr(migration, factory_name)(bind)
        constraint_names = getattr(migration, constraint_names_name)
        migration._restore_constraint_names(bind, constraint_names)

    ddl = output.getvalue()
    for names in constraint_names.values():
        for name in names:
            temporary_name = f"{name}{migration._POSTGRES_TEMP_CONSTRAINT_SUFFIX}"
            assert f"CONSTRAINT {temporary_name}" in ddl
            assert f"RENAME CONSTRAINT {temporary_name} TO {name}" in ddl
            assert f"CONSTRAINT {name} " not in ddl


def test_multi_account_upgrade_preserves_data_and_generated_ids(tmp_path):
    migration = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'upgrade.sqlite'}")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        users, characters, gacha = _create_legacy_schema(connection)
        connection.execute(
            users.insert(),
            [{"id": 7, "access_token": "access", "cred": "cred", "cred_token": "token", "user_id": None}],
        )
        connection.execute(
            characters.insert(),
            [
                {
                    "id": 7,
                    "uid": "ark-role",
                    "app_code": "arknights",
                    "channel_master_id": "1",
                    "nickname": "Doctor",
                    "isdefault": True,
                    "role_id": None,
                },
                {
                    "id": 7,
                    "uid": "ef-parent",
                    "app_code": "endfield",
                    "channel_master_id": "ef-1",
                    "nickname": "Admin",
                    "isdefault": False,
                    "role_id": "ef-role",
                },
            ],
        )
        connection.execute(
            gacha.insert(),
            [
                {
                    "id": 9,
                    "uid": 7,
                    "char_pk_id": 7,
                    "char_uid": "ark-role",
                    "pool_id": "pool",
                    "pool_name": "Pool",
                    "char_id": "item",
                    "char_name": "Item",
                    "rarity": 6,
                    "is_new": True,
                    "gacha_ts": 100,
                    "pos": 1,
                    "app_code": "arknights",
                    "item_type": "char",
                    "is_free": False,
                }
            ],
        )
        _run(connection, migration.upgrade)

        account = connection.execute(sa.text("SELECT id, owner_id, skland_user_id FROM skland_user")).mappings().one()
        roles = (
            connection.execute(
                sa.text(
                    "SELECT id, account_id, uid, role_id, app_code, is_skland_default "
                    "FROM skland_characters ORDER BY id"
                )
            )
            .mappings()
            .all()
        )
        defaults = (
            connection.execute(
                sa.text("SELECT owner_id, app_code, character_id FROM skland_character_default ORDER BY app_code")
            )
            .mappings()
            .all()
        )
        records = (
            connection.execute(sa.text("SELECT character_id, gacha_ts, pos FROM skland_gacha_record")).mappings().all()
        )

        assert account["owner_id"] == 7
        assert account["skland_user_id"] is None
        assert roles[0]["role_id"] == "ark-role"
        assert all(role["is_skland_default"] == 0 for role in roles)
        assert [item["app_code"] for item in defaults] == ["arknights", "endfield"]
        assert records == [{"character_id": roles[0]["id"], "gacha_ts": 100, "pos": 1}]

        new_account_id = connection.execute(
            sa.text(
                "INSERT INTO skland_user (owner_id, access_token, cred, cred_token, skland_user_id) "
                "VALUES (8, NULL, 'c2', 't2', 'remote-8') RETURNING id"
            )
        ).scalar_one()
        new_character_id = connection.execute(
            sa.text(
                "INSERT INTO skland_characters "
                "(account_id, uid, role_id, app_code, channel_master_id, "
                "server_name, nickname, level, is_skland_default) "
                "VALUES (:account_id, 'new', 'new', 'arknights', '1', 'Official', 'New', NULL, 0) RETURNING id"
            ),
            {"account_id": new_account_id},
        ).scalar_one()
        new_record_id = connection.execute(
            sa.text(
                "INSERT INTO skland_gacha_record "
                "(character_id, pool_id, pool_name, item_type, char_id, char_name, "
                "rarity, is_new, is_free, gacha_ts, pos) "
                "VALUES (:character_id, 'p', 'P', 'char', 'x', 'X', 6, 0, 0, 101, 1) RETURNING id"
            ),
            {"character_id": new_character_id},
        ).scalar_one()
        assert new_account_id > account["id"]
        assert new_character_id > max(role["id"] for role in roles)
        assert new_record_id > 0


def test_multi_account_upgrade_discards_unreachable_orphan_characters(tmp_path, caplog):
    migration = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'orphan.sqlite'}")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        users, characters, _gacha = _create_legacy_schema(connection)
        connection.execute(
            users.insert(),
            [{"id": 7, "access_token": "access", "cred": "cred", "cred_token": "token", "user_id": "remote"}],
        )
        connection.execute(
            characters.insert(),
            [
                {
                    "id": 7,
                    "uid": "reachable-role",
                    "app_code": "arknights",
                    "channel_master_id": "1",
                    "nickname": "Reachable",
                    "isdefault": True,
                    "role_id": None,
                },
                {
                    "id": 10,
                    "uid": "orphan-role",
                    "app_code": "arknights",
                    "channel_master_id": "1",
                    "nickname": "Orphan",
                    "isdefault": True,
                    "role_id": None,
                },
            ],
        )

        with caplog.at_level("WARNING"):
            _run(connection, migration.upgrade)

        roles = connection.execute(sa.text("SELECT uid FROM skland_characters ORDER BY uid")).scalars().all()
        assert roles == ["reachable-role"]
        assert "Discarding 1 unreachable legacy character row(s)" in caplog.text


def test_multi_account_upgrade_rejects_ownership_mismatch(tmp_path):
    migration = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'invalid.sqlite'}")
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        users, characters, gacha = _create_legacy_schema(connection)
        connection.execute(
            users.insert(),
            [
                {"id": 1, "access_token": None, "cred": "c1", "cred_token": "t1", "user_id": "u1"},
                {"id": 2, "access_token": None, "cred": "c2", "cred_token": "t2", "user_id": "u2"},
            ],
        )
        connection.execute(
            characters.insert(),
            [
                {
                    "id": 2,
                    "uid": "role",
                    "app_code": "arknights",
                    "channel_master_id": "1",
                    "nickname": "Doctor",
                    "isdefault": True,
                    "role_id": "role",
                }
            ],
        )
        connection.execute(
            gacha.insert(),
            [
                {
                    "id": 1,
                    "uid": 1,
                    "char_pk_id": 2,
                    "char_uid": "role",
                    "pool_id": "p",
                    "pool_name": "P",
                    "char_id": "x",
                    "char_name": "X",
                    "rarity": 6,
                    "is_new": False,
                    "gacha_ts": 1,
                    "pos": 1,
                    "app_code": "arknights",
                    "item_type": "char",
                    "is_free": False,
                }
            ],
        )
        with pytest.raises(RuntimeError, match="ownership mismatch"):
            _run(connection, migration.upgrade)
        transaction.rollback()


def test_multi_account_downgrade_rejects_multiple_accounts(tmp_path):
    migration = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'downgrade.sqlite'}")
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        users, _characters, _gacha = _create_legacy_schema(connection)
        connection.execute(
            users.insert(),
            [{"id": 7, "access_token": None, "cred": "c", "cred_token": "t", "user_id": "u"}],
        )
        _run(connection, migration.upgrade)
        connection.execute(
            sa.text(
                "INSERT INTO skland_user (owner_id, access_token, cred, cred_token, skland_user_id) "
                "VALUES (7, NULL, 'c2', 't2', 'u2')"
            )
        )
        with pytest.raises(RuntimeError, match="multi-account data cannot be represented"):
            _run(connection, migration.downgrade)
        transaction.rollback()
