"""fix model type

迁移 ID: 02e0764f579e
父迁移: 997049a57a3a
创建时间: 2025-04-03 08:37:11.577500

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "02e0764f579e"
down_revision: str | Sequence[str] | None = "997049a57a3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("skland_characters", schema=None) as batch_op:
        batch_op.alter_column("uid", existing_type=sa.INTEGER(), type_=sa.String(), existing_nullable=False)

    # ### end Alembic commands ###


def downgrade(name: str = "") -> None:
    if name:
        return
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("skland_characters", schema=None) as batch_op:
        batch_op.alter_column("uid", existing_type=sa.String(), type_=sa.INTEGER(), existing_nullable=False)

    # ### end Alembic commands ###
