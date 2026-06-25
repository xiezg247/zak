"""移除空的 bars schema；K 线由 VeighNa 写入 public。"""

from __future__ import annotations

from alembic import op

revision = "003_drop_bars_schema"
down_revision = "002_user_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS bars CASCADE")


def downgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS bars")
