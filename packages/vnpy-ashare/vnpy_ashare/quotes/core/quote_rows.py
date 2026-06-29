"""全市场行情行进程内缓存（与 AI context store 解耦）。"""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from vnpy_ashare.domain.market.quote_row import (
    QuoteRow,
    QuoteRowsLike,
    coerce_quote_rows,
    quote_row_from_stock_and_snapshot,
    quote_rows_by_vt,
)
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.quotes.market.cache_invalidation import on_market_quotes_updated

_lock = threading.Lock()
_rows: list[QuoteRow] = []


def _is_quote_row_list(rows: QuoteRowsLike) -> TypeGuard[list[QuoteRow]]:
    return isinstance(rows, list) and (not rows or all(isinstance(row, QuoteRow) for row in rows))


def set_market_quote_rows_cache(rows: QuoteRowsLike) -> None:
    global _rows
    with _lock:
        _rows = rows if _is_quote_row_list(rows) else coerce_quote_rows(rows)
    on_market_quotes_updated()


def peek_market_quotes_cache() -> list[QuoteRow]:
    """返回缓存行列表引用（只读；调用方不得原地修改）。"""
    with _lock:
        return _rows


def get_market_quotes_cache() -> list[QuoteRow]:
    with _lock:
        return list(_rows)


def clear_market_quote_rows_cache() -> None:
    global _rows
    with _lock:
        _rows = []
    on_market_quotes_updated()


def set_market_quotes_cache(items: Sequence[StockItem | Any], quotes: Mapping[str, QuoteSnapshot | Any]) -> None:
    """由 StockItem + QuoteSnapshot 映射构建行缓存（QuoteService 写入）。"""
    rows: list[QuoteRow] = []
    for item in items:
        tickflow_symbol = getattr(item, "tickflow_symbol", "")
        quote = quotes.get(tickflow_symbol)
        if quote is None:
            rows.append(
                QuoteRow(
                    symbol=getattr(item, "symbol", ""),
                    name=getattr(item, "name", ""),
                    vt_symbol=getattr(item, "vt_symbol", ""),
                    exchange=getattr(getattr(item, "exchange", None), "value", ""),
                )
            )
            continue
        if isinstance(item, StockItem) and isinstance(quote, QuoteSnapshot):
            rows.append(quote_row_from_stock_and_snapshot(item, quote))
        else:
            rows.append(
                QuoteRow(
                    symbol=getattr(item, "symbol", ""),
                    name=getattr(item, "name", ""),
                    vt_symbol=getattr(item, "vt_symbol", ""),
                    exchange=getattr(getattr(item, "exchange", None), "value", ""),
                    last_price=getattr(quote, "last_price", 0) or 0,
                    change_pct=getattr(quote, "change_pct", 0) or 0,
                    turnover_rate=getattr(quote, "turnover_rate", 0) or 0,
                    volume=getattr(quote, "volume", 0) or 0,
                    amount=getattr(quote, "amount", 0) or 0,
                    close=getattr(quote, "last_price", 0) or 0,
                )
            )
    set_market_quote_rows_cache(rows)


def quote_rows_by_vt_symbol(rows: QuoteRowsLike | None = None) -> dict[str, QuoteRow]:
    if rows is None:
        with _lock:
            source: QuoteRowsLike = _rows
    else:
        source = rows
    return quote_rows_by_vt(source)
