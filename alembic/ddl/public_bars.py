"""VeighNa public schema K 线表性能索引（与 vnpy_postgresql 表结构对齐）。"""

from __future__ import annotations

# interval 日 K 值为 Interval.DAILY.value → 'd'
DAILY_INTERVAL = "d"

PUBLIC_BAR_INDEX_UP: tuple[str, ...] = (
    # 单标的 tail：WHERE interval='d' AND symbol=? AND exchange=? AND datetime BETWEEN ...
    """
    CREATE INDEX IF NOT EXISTS ix_dbbardata_daily_symbol_exchange_dt
    ON public.dbbardata (symbol, exchange, datetime DESC)
    WHERE interval = 'd'
    """,
    # 批量 IN (symbol, exchange)：WHERE interval='d' AND (symbol, exchange) IN (...)
    """
    CREATE INDEX IF NOT EXISTS ix_dbbardata_daily_interval_sym_ex_dt
    ON public.dbbardata (interval, symbol, exchange, datetime DESC)
    WHERE interval = 'd'
    """,
    # 大表按时间维护 / 范围扫描（可选，与 symbol 索引互补）
    """
    CREATE INDEX IF NOT EXISTS ix_dbbardata_daily_dt_brin
    ON public.dbbardata USING brin (datetime)
    WHERE interval = 'd'
    """,
)

PUBLIC_BAR_INDEX_DOWN: tuple[str, ...] = (
    "DROP INDEX IF EXISTS public.ix_dbbardata_daily_dt_brin",
    "DROP INDEX IF EXISTS public.ix_dbbardata_daily_interval_sym_ex_dt",
    "DROP INDEX IF EXISTS public.ix_dbbardata_daily_symbol_exchange_dt",
)

PUBLIC_BAR_ANALYZE: tuple[str, ...] = (
    "ANALYZE public.dbbardata",
    "ANALYZE public.dbbaroverview",
)
