"""cache schema 磁盘缓存表（radar / 自选信号 / 板块展望 LLM）。"""

from __future__ import annotations

from ddl.cache import CACHE_DOWNGRADE, CACHE_TABLES

from alembic import op

revision = "004_cache_tables"
down_revision = "003_drop_bars_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in CACHE_TABLES:
        op.execute(statement)


def downgrade() -> None:
    for statement in CACHE_DOWNGRADE:
        op.execute(statement)
