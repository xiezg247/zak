"""进程内 L1 全市场行情缓存（collect 写入后 atomic swap，读路径优先命中）。"""

from __future__ import annotations

import os
import threading

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_lock = threading.RLock()
_quotes: dict[str, QuoteSnapshot] = {}
_rank_symbols: list[str] = []
_updated_at: str = ""
_complete: bool = False


def quote_l1_enabled() -> bool:
    return os.environ.get("ZAK_QUOTE_L1_CACHE", "").strip().lower() in _TRUTHY


def collect_defer_enrich_enabled() -> bool:
    return os.environ.get("ZAK_COLLECT_DEFER_ENRICH", "").strip().lower() in _TRUTHY


def swap_quotes(
    quotes: dict[str, QuoteSnapshot],
    *,
    updated_at: str | None = None,
    complete: bool = True,
) -> None:
    """atomic swap 全量快照（collect / Redis 写后调用）。"""
    global _quotes, _rank_symbols, _updated_at, _complete
    ordered = sorted(
        quotes.items(),
        key=lambda item: item[1].change_pct,
        reverse=True,
    )
    with _lock:
        _quotes = dict(ordered)
        _rank_symbols = [symbol for symbol, _quote in ordered]
        _updated_at = str(updated_at or "").strip()
        _complete = complete and bool(_quotes)


def clear_quote_l1_cache() -> None:
    global _quotes, _rank_symbols, _updated_at, _complete
    with _lock:
        _quotes = {}
        _rank_symbols = []
        _updated_at = ""
        _complete = False


def get_updated_at() -> str | None:
    with _lock:
        return _updated_at or None


def try_list_rank_symbols() -> list[str] | None:
    if not quote_l1_enabled():
        return None
    with _lock:
        if not _complete or not _rank_symbols:
            return None
        return list(_rank_symbols)


def try_get_quotes(tf_symbols: list[str]) -> dict[str, QuoteSnapshot] | None:
    """全部 symbol 命中 L1 时返回副本，否则 None（回退 Redis）。"""
    if not quote_l1_enabled() or not tf_symbols:
        return None
    with _lock:
        if not _quotes:
            return None
        result: dict[str, QuoteSnapshot] = {}
        for tf_symbol in tf_symbols:
            quote = _quotes.get(tf_symbol)
            if quote is None:
                return None
            result[tf_symbol] = quote
        return result


def try_get_all_quotes() -> dict[str, QuoteSnapshot] | None:
    if not quote_l1_enabled():
        return None
    with _lock:
        if not _complete or not _quotes:
            return None
        return dict(_quotes)
