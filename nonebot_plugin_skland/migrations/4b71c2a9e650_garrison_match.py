"""归档卫戍协议对局的统计及同局关联字段。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4b71c2a9e650"
down_revision: str | Sequence[str] | None = "c8d95f314a62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return
    op.create_table(
        "skland_garrison_match",
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Text(), nullable=False),
        sa.Column("record_id", sa.Text(), nullable=False),
        sa.Column("scene_id", sa.Text()),
        sa.Column("version_id", sa.Text(), nullable=False),
        sa.Column("ended_at", sa.BigInteger(), nullable=False),
        sa.Column("in_history", sa.Boolean(), nullable=False),
        sa.Column("band_id", sa.Text(), nullable=False),
        sa.Column("complete_state", sa.Integer(), nullable=False),
        sa.Column("strategy_master_victor", sa.Boolean()),
        sa.Column("bond_layers", sa.JSON(), nullable=False),
        sa.Column("duration_seconds", sa.BigInteger()),
        sa.Column("boss_kills", sa.Integer(), nullable=False),
        sa.Column("hidden_boss_kills", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["skland_characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("character_id", "activity_id", "record_id"),
    )
    op.create_index("ix_skland_garrison_match_scene", "skland_garrison_match", ["activity_id", "scene_id"])
    op.create_index(
        "ix_skland_garrison_match_history",
        "skland_garrison_match",
        ["character_id", "activity_id", "in_history", "ended_at"],
    )


def downgrade(name: str = "") -> None:
    if not name:
        op.drop_table("skland_garrison_match")
