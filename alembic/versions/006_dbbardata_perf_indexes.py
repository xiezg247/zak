"""补全 VeighNa dbbardata 日 K 性能索引（批量 IN + BRIN）。"""

from __future__ import annotations

from alembic import op

revision = "006_dbbardata_perf_indexes"
down_revision = "005_dbbardata_perf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.dbbardata') IS NOT NULL THEN
                EXECUTE 'CREATE INDEX IF NOT EXISTS ix_dbbardata_daily_interval_sym_ex_dt '
                    || 'ON public.dbbardata (interval, symbol, exchange, datetime DESC) '
                    || 'WHERE interval = ''d''';
                EXECUTE 'CREATE INDEX IF NOT EXISTS ix_dbbardata_daily_dt_brin '
                    || 'ON public.dbbardata USING brin (datetime) '
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
    op.execute("DROP INDEX IF EXISTS public.ix_dbbardata_daily_dt_brin")
    op.execute("DROP INDEX IF EXISTS public.ix_dbbardata_daily_interval_sym_ex_dt")
