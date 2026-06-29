"""VeighNa public.dbbaroverview 分页与按 key 查询（本地数据页）。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.data.minute_periods import bar_interval, is_daily_scope, normalize_period
from vnpy_ashare.domain.data.bar import PeriodBarOverview
from vnpy_ashare.storage.repository.app import AppBaseRepository

_VALID_OVERVIEW_SQL = """
    o.exchange IS NOT NULL
    AND o.start IS NOT NULL
    AND o.end IS NOT NULL
    AND o.count > 0
"""


def _interval_for_scope(scope: str) -> tuple[str, str]:
    if is_daily_scope(scope):
        return "daily", "d"
    period = normalize_period(scope)
    return period, bar_interval(period).value


def _row_to_overview(row, *, period: str) -> PeriodBarOverview:
    return PeriodBarOverview(
        symbol=str(row["symbol"]),
        exchange=Exchange(str(row["exchange"])),
        period=period,
        start=row["start"],
        end=row["end"],
        count=int(row["count"]),
    )


class BarOverviewRepository(AppBaseRepository):
    def count_scope(self, scope: str) -> int:
        period, interval = _interval_for_scope(scope)
        _ = period
        sql = f"""
            SELECT COUNT(*) AS n
            FROM public.dbbaroverview o
            WHERE o.interval = %s
              AND {_VALID_OVERVIEW_SQL}
        """

        def _query(conn):
            return conn.execute(sql, (interval,)).fetchone()

        row = self.run(_query)
        return int(row["n"]) if row is not None else 0

    def page_scope(
        self,
        scope: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[PeriodBarOverview]:
        period, interval = _interval_for_scope(scope)
        sql = f"""
            SELECT o.symbol, o.exchange, o.count, o.start, o.end
            FROM public.dbbaroverview o
            WHERE o.interval = %s
              AND {_VALID_OVERVIEW_SQL}
            ORDER BY o.symbol, o.exchange
            LIMIT %s OFFSET %s
        """
        params = (interval, max(limit, 0), max(offset, 0))

        def _query(conn):
            return conn.execute(sql, params).fetchall()

        rows = self.run(_query)
        return [_row_to_overview(row, period=period) for row in rows]

    def search_scope_page(
        self,
        scope: str,
        keyword: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PeriodBarOverview], int]:
        keyword = keyword.strip().lower()
        if not keyword:
            total = self.count_scope(scope)
            items = self.page_scope(scope, offset=offset, limit=limit)
            return items, total

        period, interval = _interval_for_scope(scope)
        pattern = f"%{keyword}%"
        base_from = f"""
            FROM public.dbbaroverview o
            LEFT JOIN app.universe u
              ON u.symbol = o.symbol AND u.exchange = o.exchange
            WHERE o.interval = %s
              AND {_VALID_OVERVIEW_SQL}
              AND (
                lower(o.symbol) LIKE %s
                OR lower(COALESCE(u.name, '')) LIKE %s
              )
        """
        count_sql = f"SELECT COUNT(*) AS n {base_from}"
        page_sql = f"""
            SELECT o.symbol, o.exchange, o.count, o.start, o.end
            {base_from}
            ORDER BY o.symbol, o.exchange
            LIMIT %s OFFSET %s
        """
        count_params = (interval, pattern, pattern)
        page_params = (interval, pattern, pattern, max(limit, 0), max(offset, 0))

        def _query(conn):
            total_row = conn.execute(count_sql, count_params).fetchone()
            total = int(total_row["n"]) if total_row is not None else 0
            rows = conn.execute(page_sql, page_params).fetchall()
            return total, rows

        total, rows = self.run(_query)
        return [_row_to_overview(row, period=period) for row in rows], total

    def fetch_scope_overview(
        self,
        symbol: str,
        exchange: Exchange,
        scope: str,
    ) -> PeriodBarOverview | None:
        period, interval = _interval_for_scope(scope)
        sql = f"""
            SELECT o.symbol, o.exchange, o.count, o.start, o.end
            FROM public.dbbaroverview o
            WHERE o.interval = %s
              AND o.symbol = %s
              AND o.exchange = %s
              AND {_VALID_OVERVIEW_SQL}
            LIMIT 1
        """
        params = (interval, symbol, exchange.value)

        def _query(conn):
            return conn.execute(sql, params).fetchone()

        row = self.run(_query)
        if row is None:
            return None
        return _row_to_overview(row, period=period)

    def fetch_scope_overviews_for_keys(
        self,
        keys: list[tuple[str, Exchange]],
        scope: str,
    ) -> dict[tuple[str, Exchange], PeriodBarOverview]:
        if not keys:
            return {}
        unique_keys = list(dict.fromkeys(keys))
        period, interval = _interval_for_scope(scope)
        placeholders = ", ".join("(%s, %s)" for _ in unique_keys)
        params: list[object] = [interval]
        for symbol, exchange in unique_keys:
            params.extend((symbol, exchange.value))
        sql = f"""
            SELECT o.symbol, o.exchange, o.count, o.start, o.end
            FROM public.dbbaroverview o
            WHERE o.interval = %s
              AND {_VALID_OVERVIEW_SQL}
              AND (o.symbol, o.exchange) IN ({placeholders})
        """

        def _query(conn):
            return conn.execute(sql, tuple(params)).fetchall()

        rows = self.run(_query)
        return {(str(row["symbol"]), Exchange(str(row["exchange"]))): _row_to_overview(row, period=period) for row in rows}


_repo = BarOverviewRepository()


def count_scope_bar_overviews(scope: str = "daily") -> int:
    return _repo.count_scope(scope)


def page_scope_bar_overviews(
    scope: str = "daily",
    *,
    offset: int = 0,
    limit: int = 50,
) -> list[PeriodBarOverview]:
    return _repo.page_scope(scope, offset=offset, limit=limit)


def search_scope_bar_overviews_page(
    scope: str,
    keyword: str,
    *,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[PeriodBarOverview], int]:
    return _repo.search_scope_page(scope, keyword, offset=offset, limit=limit)


def fetch_scope_bar_overview(
    symbol: str,
    exchange: Exchange,
    scope: str,
) -> PeriodBarOverview | None:
    return _repo.fetch_scope_overview(symbol, exchange, scope)


def fetch_scope_bar_overviews_for_keys(
    keys: list[tuple[str, Exchange]],
    scope: str,
) -> dict[tuple[str, Exchange], PeriodBarOverview]:
    return _repo.fetch_scope_overviews_for_keys(keys, scope)
