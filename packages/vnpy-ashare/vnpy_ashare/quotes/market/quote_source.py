"""全市场行情行统一获取（盘中 Redis / 失败或盘外 Tushare 收盘）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRowsLike
from vnpy_ashare.domain.screener.quotes_snapshot import MarketQuotesSnapshot
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.quotes.core.screening_snapshot_router import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError

__all__ = [
    "load_intraday_market_snapshot",
    "load_quote_rows_for_market",
    "peek_market_quote_rows",
    "probe_intraday_market_quotes",
    "quote_rows_from_tushare_fallback",
    "resolve_intraday_quote_rows",
]


def _format_eod_updated_at(updated_at: str | None) -> str | None:
    """YYYYMMDD → YYYY-MM-DD，便于状态栏识别收盘日。"""
    text = str(updated_at or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text or None


def quote_rows_from_tushare_fallback() -> tuple[QuoteRowsLike, str | None]:
    """用 Tushare daily_basic + daily 涨跌幅构造广度/榜单样本（上一可用交易日）。"""
    from vnpy_ashare.screener.data.data_source import load_tushare_eod_snapshot

    try:
        snapshot = load_tushare_eod_snapshot()
    except Exception:
        return [], None
    if snapshot is None or not snapshot.rows:
        return [], None
    rows: list[dict[str, Any]] = []
    for row in snapshot.rows:
        rows.append(
            {
                "change_pct": row.get("change_pct"),
                "volume": row.get("volume", 0),
                "amount": row.get("amount", 0),
                "vt_symbol": row.get("vt_symbol", ""),
                "symbol": row.get("symbol", ""),
                "name": row.get("name", ""),
                "last_price": row.get("last_price") or row.get("close"),
                "turnover_rate": row.get("turnover_rate", 0),
                "volume_ratio": row.get("volume_ratio", 0),
                "net_mf_amount": row.get("net_mf_amount", 0),
                "limit_times": row.get("limit_times", 0),
                "source": "tushare",
            }
        )
    return rows, _format_eod_updated_at(snapshot.updated_at)


def _intraday_snapshot(*, enrich_factors: bool = True) -> MarketQuotesSnapshot:
    """盘中统一入口：ScreeningContext → 进程 Hub → Redis。"""
    _ = enrich_factors  # enrich 在 loader / uncached 路径内处理
    return load_screening_quote_snapshot()


def load_quote_rows_for_market(*, allow_network: bool = True, force: bool = False) -> tuple[QuoteRowsLike, str | None]:
    """市场页/情绪周期等共用的行情行加载入口。"""
    if not is_ashare_trading_session():
        return quote_rows_from_tushare_fallback()
    if not allow_network and not force:
        from vnpy_ashare.quotes.core.quote_rows import peek_market_quotes_cache

        cached = peek_market_quotes_cache()
        if cached:
            return cached, None
        return [], None
    try:
        snapshot = _intraday_snapshot()
    except (MarketQuotesLoadError, RuntimeError):
        return quote_rows_from_tushare_fallback()
    # 盘中筛选快照可能已是 Tushare 回退（source=tushare）
    if str(getattr(snapshot, "source", "") or "") == "tushare":
        return snapshot.rows, _format_eod_updated_at(snapshot.updated_at)
    return snapshot.rows, snapshot.updated_at


def peek_market_quote_rows(*, min_rows: int = 0) -> QuoteRowsLike | None:
    from vnpy_ashare.quotes.core.quote_rows import peek_market_quotes_cache

    cached = peek_market_quotes_cache()
    if cached and len(cached) >= min_rows:
        return cached
    return None


def load_intraday_market_snapshot(*, enrich_factors: bool = True) -> MarketQuotesSnapshot:
    return _intraday_snapshot(enrich_factors=enrich_factors)


def probe_intraday_market_quotes(*, enrich_factors: bool = False) -> None:
    """探测 Redis 全市场行情是否可用；不可用则抛出 MarketQuotesLoadError。"""
    load_intraday_market_snapshot(enrich_factors=enrich_factors)


def resolve_intraday_quote_rows(
    *,
    min_cached_rows: int = 0,
    enrich_factors: bool = True,
) -> tuple[QuoteRowsLike, str | None, int, str | None]:
    """盘中优先缓存，否则拉全市场快照；Redis 失败时回退 Tushare 收盘。"""
    cached = peek_market_quote_rows(min_rows=min_cached_rows)
    if cached is not None:
        return cached, None, len(cached), None
    try:
        market = _intraday_snapshot(enrich_factors=enrich_factors)
    except MarketQuotesLoadError as ex:
        rows, updated_at = quote_rows_from_tushare_fallback()
        if rows:
            return rows, updated_at, len(rows), None
        return [], None, 0, str(ex)
    updated_at = market.updated_at
    if str(getattr(market, "source", "") or "") == "tushare":
        updated_at = _format_eod_updated_at(updated_at)
    return market.rows, updated_at, market.total, None
