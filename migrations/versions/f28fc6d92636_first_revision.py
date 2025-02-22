"""first revision

迁移 ID: f28fc6d92636
父迁移:
创建时间: 2025-02-22 14:45:29.432938

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f28fc6d92636"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("first_revision",)
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "skland_characters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uid", sa.Integer(), nullable=False),
        sa.Column("app_code", sa.Text(), nullable=False),
        sa.Column("channel_master_id", sa.Text(), nullable=False),
        sa.Column("nickname", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", "uid", name=op.f("pk_skland_characters")),
        info={"bind_key": "nonebot_plugin_skland"},
    )
    op.create_table(
        "skland_user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("cred", sa.Text(), nullable=False),
        sa.Column("cred_token", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skland_user")),
        info={"bind_key": "nonebot_plugin_skland"},
    )
    # ### end Alembic commands ###


def downgrade(name: str = "") -> None:
    if name:
        return
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("skland_user")
    op.drop_table("skland_characters")
    # ### end Alembic commands ###
