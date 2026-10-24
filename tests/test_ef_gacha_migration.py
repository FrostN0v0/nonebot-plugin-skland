from pathlib import Path
from runpy import run_path

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.migration import MigrationContext


def test_pool_period_upgrade_keeps_unknown_history_and_role_constraints(tmp_path):
    migration = run_path(str(Path("nonebot_plugin_skland/migrations/c8d95f314a62_ef_gacha_pool_version.py")))
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'period.sqlite3'}")
    metadata = sa.MetaData()
    roles = sa.Table("skland_characters", metadata, sa.Column("id", sa.Integer, primary_key=True))
    records = sa.Table(
        "skland_gacha_record",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("character_id", sa.Integer, sa.ForeignKey("skland_characters.id"), nullable=False),
        sa.Column("pool_id", sa.Text, nullable=False),
        sa.Column("gacha_ts", sa.BigInteger, nullable=False),
        sa.Column("pos", sa.Integer, nullable=False),
        sa.UniqueConstraint("character_id", "gacha_ts", "pos", name="uq_skland_gacha_character_ts_pos"),
    )
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        metadata.create_all(connection)
        connection.execute(roles.insert(), [{"id": 1}, {"id": 2}])
        original = [
            {"id": 1, "character_id": 1, "pool_id": "rerun_wpn_yvonne", "gacha_ts": 100, "pos": 1},
            {"id": 2, "character_id": 2, "pool_id": "rerun_wpn_yvonne", "gacha_ts": 100, "pos": 1},
        ]
        connection.execute(records.insert(), original)
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration["upgrade"]()
        rows = connection.execute(sa.text("SELECT * FROM skland_gacha_record ORDER BY id")).mappings().all()
        assert [dict(row) for row in rows] == [dict(row, pool_version=None) for row in original]
        connection.execute(sa.text("UPDATE skland_gacha_record SET pool_version=1 WHERE id=1"))
        connection.execute(
            sa.text(
                "INSERT INTO skland_gacha_record (id,character_id,pool_id,gacha_ts,pos,pool_version) "
                "VALUES (3,1,'rerun_wpn_yvonne',200,2,2)"
            )
        )
        assert connection.execute(
            sa.text("SELECT pool_version FROM skland_gacha_record ORDER BY id")
        ).scalars().all() == [
            1,
            None,
            2,
        ]
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert sa.inspect(connection).get_unique_constraints("skland_gacha_record")[0]["column_names"] == [
            "character_id",
            "gacha_ts",
            "pos",
        ]
        with Operations.context(context):
            migration["downgrade"]()
        assert "pool_version" not in {
            column["name"] for column in sa.inspect(connection).get_columns("skland_gacha_record")
        }
        assert connection.execute(sa.text("SELECT id,pool_id,pos FROM skland_gacha_record ORDER BY id")).all() == [
            (1, "rerun_wpn_yvonne", 1),
            (2, "rerun_wpn_yvonne", 1),
            (3, "rerun_wpn_yvonne", 2),
        ]
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    engine.dispose()
