"""全市场行情行统一获取（盘中 Redis / 盘外 Tushare）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRowsLike
from vnpy_ashare.domain.screener.quotes_snapshot import MarketQuotesSnapshot
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.quotes.core.quote_rows import get_market_quotes_cache
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError, load_market_quote_rows

__all__ = [
    "load_intraday_market_snapshot",
    "load_quote_rows_for_market",
    "peek_market_quote_rows",
    "probe_intraday_market_quotes",
    "quote_rows_from_tushare_fallback",
    "resolve_intraday_quote_rows",
]


def quote_rows_from_tushare_fallback() -> tuple[QuoteRowsLike, str | None]:
    """盘外用 Tushare daily_basic + daily 涨跌幅构造广度样本。"""
    from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot_uncached

    try:
        snapshot = load_screening_quote_snapshot_uncached()
    except Exception:
        return [], None
    rows: list[dict[str, Any]] = []
    for row in snapshot.rows:
        rows.append(
            {
                "change_pct": row.get("change_pct"),
                "amount": row.get("amount", 0),
                "vt_symbol": row.get("vt_symbol", ""),
            }
        )
    updated_at = snapshot.updated_at
    if updated_at and len(updated_at) == 8 and updated_at.isdigit():
        updated_at = f"{updated_at[:4]}-{updated_at[4:6]}-{updated_at[6:8]}"
    return rows, updated_at


def load_quote_rows_for_market(*, allow_network: bool = True, force: bool = False) -> tuple[QuoteRowsLike, str | None]:
    """市场页/情绪周期等共用的行情行加载入口。"""
    if not is_ashare_trading_session():
        return quote_rows_from_tushare_fallback()
    if not force:
        cached = get_market_quotes_cache()
        if cached:
            return cached, None
    if not allow_network:
        return [], None
    try:
        snapshot = load_market_quote_rows()
    except MarketQuotesLoadError:
        return [], None
    return snapshot.rows, snapshot.updated_at


def peek_market_quote_rows(*, min_rows: int = 0) -> QuoteRowsLike | None:
    cached = get_market_quotes_cache()
    if cached and len(cached) >= min_rows:
        return cached
    return None


def load_intraday_market_snapshot(*, enrich_factors: bool = True) -> MarketQuotesSnapshot:
    return load_market_quote_rows(enrich_factors=enrich_factors)


def probe_intraday_market_quotes(*, enrich_factors: bool = False) -> None:
    """探测 Redis 全市场行情是否可用；不可用则抛出 MarketQuotesLoadError。"""
    load_intraday_market_snapshot(enrich_factors=enrich_factors)


def resolve_intraday_quote_rows(
    *,
    min_cached_rows: int = 0,
    enrich_factors: bool = True,
) -> tuple[QuoteRowsLike, str | None, int, str | None]:
    """盘中优先 Redis 缓存，否则拉全市场快照（不做盘外 Tushare 回退）。"""
    cached = peek_market_quote_rows(min_rows=min_cached_rows)
    if cached is not None:
        return cached, None, len(cached), None
    try:
        market = load_market_quote_rows(enrich_factors=enrich_factors)
    except MarketQuotesLoadError as ex:
        return [], None, 0, str(ex)
    return market.rows, market.updated_at, market.total, None
