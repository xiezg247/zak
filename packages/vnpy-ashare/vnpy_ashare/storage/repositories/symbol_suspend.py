"""标的停牌日 repository。"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.time.calendar import last_trading_day
from vnpy_ashare.integrations.tushare.suspend import fetch_suspend_d
from vnpy_ashare.storage.repository.app import MetaRepository
from vnpy_ashare.storage.repositories.trade_calendar import load_open_trading_days
from vnpy_common.storage.repository import BaseRepository, bulk_upsert
from vnpy_common.storage.tables import symbol_suspend_days as ssd

SUSPEND_SYNCED_AT_KEY = "symbol_suspend_synced_at"
SUSPEND_LAST_TRADE_DATE_KEY = "symbol_suspend_last_trade_date"
DEFAULT_LOOKBACK_DAYS = 3

_meta = MetaRepository()


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _format_date(value: date) -> str:
    return value.isoformat()


class SymbolSuspendRepository(BaseRepository):
    table = ssd

    def upsert_rows(self, rows: list[tuple[str, str, str, str]]) -> int:
        if not rows:
            return 0
        values = [
            {
                "symbol": symbol,
                "exchange": exchange,
                "cal_date": cal_date,
                "suspend_type": suspend_type,
            }
            for symbol, exchange, cal_date, suspend_type in rows
        ]

        def _write(conn) -> None:
            bulk_upsert(
                conn,
                self.table,
                values,
                conflict_columns=("symbol", "exchange", "cal_date"),
                update_columns=("suspend_type",),
            )

        self.run(_write)
        return len(rows)

    def load_days(
        self,
        symbol: str,
        exchange: Exchange | str,
        start: date,
        end: date,
    ) -> set[date]:
        if start > end:
            return set()
        exchange_value = exchange.value if isinstance(exchange, Exchange) else str(exchange)
        rows = self.fetchall(
            select(ssd.c.cal_date).where(
                ssd.c.symbol == symbol,
                ssd.c.exchange == exchange_value,
                ssd.c.cal_date >= _format_date(start),
                ssd.c.cal_date <= _format_date(end),
            )
        )
        return {_parse_date(str(row[0])) for row in rows}

    def load_keys(self, trade_date: date) -> frozenset[tuple[str, str]]:
        rows = self.fetchall(
            select(ssd.c.symbol, ssd.c.exchange).where(ssd.c.cal_date == _format_date(trade_date))
        )
        return frozenset((str(row[0]), str(row[1])) for row in rows)

    def clear_cache(self) -> None:
        def _write(conn) -> None:
            conn.execute_stmt(delete(ssd))

        self.run(_write)
        _meta.delete_keys(SUSPEND_SYNCED_AT_KEY, SUSPEND_LAST_TRADE_DATE_KEY)


_repo = SymbolSuspendRepository()


def sync_suspend_for_date(trade_date: date) -> int:
    """同步单个交易日的停牌记录，返回写入条数。"""
    rows = fetch_suspend_d(trade_date)
    payload = [(row["symbol"], row["exchange"], row["cal_date"], row["suspend_type"]) for row in rows]
    count = _repo.upsert_rows(payload)
    _meta.upsert_value(SUSPEND_LAST_TRADE_DATE_KEY, _format_date(trade_date))
    _meta.upsert_value(SUSPEND_SYNCED_AT_KEY, datetime.now().isoformat())
    return count


def sync_suspend_recent(*, lookback_days: int = DEFAULT_LOOKBACK_DAYS, end: date | None = None) -> tuple[int, list[date]]:
    """同步最近若干 A 股交易日的停牌记录（增量幂等）。"""
    latest = end or last_trading_day()
    start = latest - timedelta(days=max(lookback_days * 2, 14))
    trading_days = load_open_trading_days(start, latest)
    if not trading_days:
        return 0, []
    recent = trading_days[-lookback_days:]
    total = 0
    for day in recent:
        total += sync_suspend_for_date(day)
    return total, recent


def load_suspend_days(
    symbol: str,
    exchange: Exchange | str,
    start: date,
    end: date,
) -> set[date]:
    """读取 [start, end] 内已知停牌日。"""
    return _repo.load_days(symbol, exchange, start, end)


def load_suspended_keys(trade_date: date) -> frozenset[tuple[str, str]]:
    """指定交易日全市场停牌标的 (symbol, exchange)。"""
    return _repo.load_keys(trade_date)


def ensure_suspend_keys_for_screening(*, trade_date: date | None = None) -> frozenset[tuple[str, str]]:
    """选股硬过滤用：读取当日停牌列表，本地无缓存时尝试增量同步一次。"""
    day = trade_date or last_trading_day()
    keys = load_suspended_keys(day)
    if keys:
        return keys
    try:
        sync_suspend_for_date(day)
    except Exception:
        return frozenset()
    return load_suspended_keys(day)


def clear_symbol_suspend_cache() -> None:
    """测试用：清空停牌日缓存。"""
    _repo.clear_cache()
