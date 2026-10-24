"""保留终末地重构卡池期次。

Migration ID: c8d95f314a62
Parent migration: 6f2c3a9b8d71
Created: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d95f314a62"
down_revision: str | Sequence[str] | None = "6f2c3a9b8d71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return
    op.add_column("skland_gacha_record", sa.Column("pool_version", sa.Integer(), nullable=True))


def downgrade(name: str = "") -> None:
    if name:
        return
    with op.batch_alter_table("skland_gacha_record") as batch:
        batch.drop_column("pool_version")
