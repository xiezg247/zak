"""初始 schema：app / chat / auth / cache / system / bars。"""

from __future__ import annotations

from alembic import op

from ddl.initial import ALL_STATEMENTS, DOWNGRADE_STATEMENTS

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in ALL_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
