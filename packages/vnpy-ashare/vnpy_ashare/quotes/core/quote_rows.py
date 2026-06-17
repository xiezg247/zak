"""全市场行情行进程内缓存（与 AI context store 解耦）。"""

from __future__ import annotations

import threading
from typing import Any

from vnpy_ashare.quotes.market.cache_invalidation import on_market_quotes_updated

_lock = threading.Lock()
_rows: list[dict[str, Any]] = []


def set_market_quote_rows_cache(rows: list[dict[str, Any]]) -> None:
    global _rows
    with _lock:
        _rows = [dict(row) for row in rows]
    on_market_quotes_updated()


def get_market_quotes_cache() -> list[dict[str, Any]]:
    with _lock:
        return list(_rows)


def clear_market_quote_rows_cache() -> None:
    global _rows
    with _lock:
        _rows = []


def set_market_quotes_cache(items: list[Any], quotes: dict[str, Any]) -> None:
    """由 StockItem + QuoteSnapshot 映射构建行缓存（QuoteService 写入）。"""
    rows: list[dict[str, Any]] = []
    for item in items:
        tickflow_symbol = getattr(item, "tickflow_symbol", "")
        quote = quotes.get(tickflow_symbol)
        rows.append(
            {
                "symbol": getattr(item, "symbol", ""),
                "name": getattr(item, "name", ""),
                "vt_symbol": getattr(item, "vt_symbol", ""),
                "last_price": getattr(quote, "last_price", 0) if quote else 0,
                "change_pct": getattr(quote, "change_pct", 0) if quote else 0,
                "turnover_rate": getattr(quote, "turnover_rate", 0) if quote else 0,
                "volume": getattr(quote, "volume", 0) if quote else 0,
                "amount": getattr(quote, "amount", 0) if quote else 0,
            }
        )
    set_market_quote_rows_cache(rows)


def quote_rows_by_vt_symbol(rows: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    source = rows if rows is not None else get_market_quotes_cache()
    return {str(row.get("vt_symbol") or "").strip(): row for row in source if row.get("vt_symbol")}
