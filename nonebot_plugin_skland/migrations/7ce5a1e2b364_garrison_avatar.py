"""保存卫戍对局队友摘要所用的角色头像。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7ce5a1e2b364"
down_revision: str | Sequence[str] | None = "4b71c2a9e650"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if not name:
        op.add_column("skland_characters", sa.Column("garrison_avatar_url", sa.Text(), nullable=True))


def downgrade(name: str = "") -> None:
    if not name:
        # Do not rebuild the referenced character table: that would cascade into the archives on SQLite.
        op.drop_column("skland_characters", "garrison_avatar_url")
