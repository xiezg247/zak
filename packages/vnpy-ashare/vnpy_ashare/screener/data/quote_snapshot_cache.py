"""选股行情快照上下文读取（打破 data_source ↔ screening_context 循环）。"""

from __future__ import annotations

from collections.abc import Callable

from vnpy_ashare.screener.data.quotes_loader import MarketQuotesSnapshot

_reader: Callable[[], MarketQuotesSnapshot | None] | None = None


def register_cached_quote_snapshot_reader(reader: Callable[[], MarketQuotesSnapshot | None]) -> None:
    global _reader
    _reader = reader


def read_cached_quote_snapshot() -> MarketQuotesSnapshot | None:
    if _reader is None:
        return None
    return _reader()
