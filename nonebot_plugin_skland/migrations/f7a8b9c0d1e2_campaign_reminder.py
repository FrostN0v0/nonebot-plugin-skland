"""campaign reminder

Migration ID: f7a8b9c0d1e2
Parent migration: a689da19471b
Created at: 2026-06-07

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | Sequence[str] | None = "a689da19471b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return
    op.create_table(
        "skland_campaign_reminder",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("notify_target", sa.Text(), nullable=False),
        sa.Column("platform_user_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["skland_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_skland_campaign_reminder")),
        info={"bind_key": "nonebot_plugin_skland"},
    )


def downgrade(name: str = "") -> None:
    if name:
        return
    op.drop_table("skland_campaign_reminder")
