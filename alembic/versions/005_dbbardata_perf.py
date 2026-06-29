"""VeighNa public.dbbardata 日 K 尾部查询索引与统计信息维护。"""

from __future__ import annotations

from alembic import op

revision = "005_dbbardata_perf"
down_revision = "004_cache_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.dbbardata') IS NOT NULL THEN
                EXECUTE 'CREATE INDEX IF NOT EXISTS ix_dbbardata_daily_symbol_exchange_dt '
                    || 'ON public.dbbardata (symbol, exchange, datetime DESC) '
                    || 'WHERE interval = ''d''';
                EXECUTE 'ANALYZE public.dbbardata';
            END IF;
            IF to_regclass('public.dbbaroverview') IS NOT NULL THEN
                EXECUTE 'ANALYZE public.dbbaroverview';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_dbbardata_daily_symbol_exchange_dt")
