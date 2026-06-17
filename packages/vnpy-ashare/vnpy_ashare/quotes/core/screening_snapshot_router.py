"""选股行情快照路由（带 ScreeningContext 缓存）。"""

from __future__ import annotations

from collections.abc import Callable

from vnpy_ashare.screener.data.quote_snapshot_cache import read_cached_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesSnapshot

_uncached_loader: Callable[[], MarketQuotesSnapshot] | None = None


def register_uncached_quote_snapshot_loader(loader: Callable[[], MarketQuotesSnapshot]) -> None:
    global _uncached_loader
    _uncached_loader = loader


def load_screening_quote_snapshot() -> MarketQuotesSnapshot:
    cached = read_cached_quote_snapshot()
    if cached is not None:
        return cached
    if _uncached_loader is None:
        raise RuntimeError("选股行情快照未注册 uncached loader")
    return _uncached_loader()
