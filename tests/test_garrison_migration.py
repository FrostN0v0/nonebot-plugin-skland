from pathlib import Path
from runpy import run_path

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.migration import MigrationContext


def test_garrison_upgrade_downgrade_preserves_roles_and_gacha_records():
    migration = run_path(str(Path("nonebot_plugin_skland/migrations/4b71c2a9e650_garrison_match.py")))
    engine = sa.create_engine("sqlite://")
    with engine.begin() as db:
        db.exec_driver_sql("PRAGMA foreign_keys=ON")
        db.exec_driver_sql("CREATE TABLE skland_characters (id INTEGER PRIMARY KEY)")
        db.exec_driver_sql(
            "CREATE TABLE skland_gacha_record (character_id INTEGER REFERENCES skland_characters(id) "
            "ON DELETE CASCADE, record_id TEXT)"
        )
        db.exec_driver_sql("INSERT INTO skland_characters VALUES (1), (2)")
        db.exec_driver_sql("INSERT INTO skland_gacha_record VALUES (1, 'pull-1'), (2, 'pull-2')")
        with Operations.context(MigrationContext.configure(db)):
            migration["upgrade"]()

        matches = sa.Table("skland_garrison_match", sa.MetaData(), autoload_with=db)
        match = {
            "activity_id": "activity",
            "record_id": "joint-match",
            "scene_id": "joint-scene",
            "version_id": "version",
            "ended_at": 100,
            "in_history": True,
            "band_id": "band",
            "complete_state": 1,
            "bond_layers": {"bond": 0},
            "boss_kills": 1,
            "hidden_boss_kills": 0,
        }
        db.execute(matches.insert(), [dict(match, character_id=1), dict(match, character_id=2)])
        assert db.execute(
            sa.select(matches.c.character_id, matches.c.bond_layers).order_by(matches.c.character_id)
        ).all() == [(1, {"bond": 0}), (2, {"bond": 0})]
        assert db.exec_driver_sql("SELECT * FROM skland_characters ORDER BY id").all() == [(1,), (2,)]
        assert db.exec_driver_sql("SELECT * FROM skland_gacha_record ORDER BY character_id").all() == [
            (1, "pull-1"),
            (2, "pull-2"),
        ]

        with Operations.context(MigrationContext.configure(db)):
            migration["downgrade"]()
        assert not sa.inspect(db).has_table("skland_garrison_match")
        assert db.exec_driver_sql("SELECT * FROM skland_characters ORDER BY id").all() == [(1,), (2,)]
        assert db.exec_driver_sql("SELECT * FROM skland_gacha_record ORDER BY character_id").all() == [
            (1, "pull-1"),
            (2, "pull-2"),
        ]
        assert not db.exec_driver_sql("PRAGMA foreign_key_check").all()
    engine.dispose()
