"""市场页大盘概览数据加载（主要指数 + 市场广度 + 行业榜）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.breadth import MarketBreadthSnapshot
from vnpy_ashare.domain.market.overview import MarketOverviewData, SectorRankItem
from vnpy_ashare.domain.market.quote_row import QuoteRowsLike
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.time.calendar import last_trading_day
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.domain.time.quote_time import normalize_datetime_text
from vnpy_ashare.integrations.tickflow.quotes import fetch_index_ticker
from vnpy_ashare.integrations.tushare.factor_fallback import resolve_latest_factor_trade_date
from vnpy_ashare.integrations.tushare.factors import fetch_daily_pct_map, fetch_daily_turnover_total_yuan, fetch_industry_l2_to_l1_map, fetch_limit_list_d
from vnpy_ashare.quotes.market.market_breadth import compute_market_breadth, merge_official_limit_counts
from vnpy_ashare.quotes.market.market_environment import load_market_environment
from vnpy_ashare.quotes.market.market_overview_cache import (
    peek_cached_indices,
    peek_market_overview_data,
    store_cached_indices,
    store_market_overview_data,
)
from vnpy_ashare.quotes.market.quote_source import load_quote_rows_for_market
from vnpy_ashare.screener.sector.sector_summary import attach_industry, compute_sector_distribution

__all__ = [
    "MarketOverviewData",
    "SECTOR_MIN_STOCKS",
    "SECTOR_TOP_N",
    "SectorRankItem",
    "is_market_overview_stale",
    "load_market_overview",
]

SECTOR_TOP_N = 10
SECTOR_MIN_STOCKS = 3


def _load_off_session_breadth(*, trade_date: str, force: bool) -> MarketBreadthSnapshot | None:
    pct_map = fetch_daily_pct_map(trade_date)
    if not pct_map:
        return None
    rows = [{"change_pct": value, "amount": 0.0} for value in pct_map.values()]
    updated_at = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
    breadth = compute_market_breadth(rows, updated_at=updated_at)
    try:
        limit_rows, _ = fetch_limit_list_d(trade_date=trade_date)
        if limit_rows:
            from vnpy_ashare.quotes.market.market_breadth import count_limit_from_rows

            limit_up, limit_down = count_limit_from_rows(limit_rows)
            breadth = breadth.model_copy(
                update={"limit_up": limit_up, "limit_down": limit_down, "limit_source": "tushare"},
            )
    except Exception:
        pass
    total_amount = fetch_daily_turnover_total_yuan(trade_date, force=force)
    if total_amount > 0:
        breadth = breadth.model_copy(update={"total_amount": total_amount})
    return breadth


def _fetch_sorted_indices() -> list[tuple[str, QuoteSnapshot]]:
    indices = fetch_index_ticker()
    indices.sort(key=lambda item: item[1].change_pct, reverse=True)
    return indices


def load_sector_ranks(rows: QuoteRowsLike, *, top_n: int = SECTOR_TOP_N) -> list[SectorRankItem]:
    """按申万 L2 行业平均涨幅排序，返回 Top N。"""
    if not rows:
        return []
    enriched = attach_industry(rows)
    if not enriched:
        return []
    stats = compute_sector_distribution(enriched, top_n=top_n, min_stocks=SECTOR_MIN_STOCKS)
    l2_to_l1: dict[str, str] = {}
    try:
        l2_to_l1 = fetch_industry_l2_to_l1_map()
    except Exception:
        l2_to_l1 = {}
    return [
        SectorRankItem(
            industry=str(item["industry"]),
            industry_l1=(l2_to_l1.get(str(item["industry"])) or None),
            count=int(item["count"]),
            avg_change_pct=float(item["avg_change_pct"]),
        )
        for item in stats
    ]


def _load_breadth(
    rows: QuoteRowsLike,
    *,
    updated_at: str | None,
    merge_official: bool = True,
) -> MarketBreadthSnapshot | None:
    if not rows:
        return None
    breadth = compute_market_breadth(rows, updated_at=updated_at)
    if merge_official:
        return merge_official_limit_counts(breadth)
    return breadth


def _latest_trade_date_str() -> str:
    return last_trading_day().strftime("%Y%m%d")


def _breadth_trade_date(updated_at: str | None) -> str | None:
    text = normalize_datetime_text(updated_at or "")
    if not text:
        return None
    if "T" in text:
        date_part = text.split("T", 1)[0]
        if len(date_part) >= 10 and date_part[4] == "-" and date_part[7] == "-":
            return date_part.replace("-", "")
        return None
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10].replace("-", "")
    if len(text) >= 8 and text[:8].isdigit():
        return text[:8]
    return None


def _is_intraday_snapshot_timestamp(updated_at: str | None) -> bool:
    """盘外若仍带时分秒，说明是 Redis 盘中快照而非日终因子。"""
    text = normalize_datetime_text(updated_at or "")
    if not text:
        return False
    if "T" in text:
        return True
    if " " in text:
        time_part = text.split(" ", 1)[1]
        return ":" in time_part
    return len(text) <= 8 and ":" in text


def is_market_overview_stale(
    data: MarketOverviewData,
    *,
    factor_trade_date: str | None = None,
) -> bool:
    """盘外概览若关键指标日期落后于最新可用因子日，视为需刷新。"""
    calendar_latest = last_trading_day().strftime("%Y%m%d")
    if not is_ashare_trading_session():
        breadth = data.breadth
        if breadth is not None and _is_intraday_snapshot_timestamp(breadth.updated_at):
            return True
    latest = factor_trade_date or resolve_latest_factor_trade_date()
    env = data.environment
    if env is not None and env.north_trade_date and env.north_trade_date < calendar_latest:
        return True
    if env is not None and env.north_trade_date and env.north_trade_date < latest:
        return True
    if env is not None and env.fear_greed_trade_date and env.fear_greed_trade_date < latest:
        return True
    breadth = data.breadth
    if breadth is not None:
        breadth_date = _breadth_trade_date(breadth.updated_at)
        if breadth_date is not None and breadth_date < latest:
            return True
    return False


def load_market_overview(*, intraday: bool = True, force: bool = False) -> MarketOverviewData:
    """拉取主要指数、市场广度与行业榜。

    非交易时段仅读缓存或轻量指数/环境，跳过行业榜与 Tushare 涨跌停校正。
    ``force=True`` 时跳过盘外 peek 短路，并重拉环境指标与行情广度。
    """
    if not intraday and not force:
        cached = peek_market_overview_data(intraday=False)
        if cached is not None:
            indices = peek_cached_indices(intraday=False)
            if indices is None:
                try:
                    indices = _fetch_sorted_indices()
                    store_cached_indices(indices)
                except Exception:
                    indices = list(cached.indices)
            data = cached.model_copy(update={"indices": indices})
            store_market_overview_data(data)
            return data

    allow_network = intraday or force
    factor_date = resolve_latest_factor_trade_date()
    rows, updated_at = load_quote_rows_for_market(allow_network=allow_network, force=force)
    indices = _fetch_sorted_indices()
    store_cached_indices(indices)
    environment = load_market_environment(force=force, factor_trade_date=factor_date)

    if not intraday:
        cached = peek_market_overview_data(intraday=False) if not force else None
        breadth = _load_breadth(rows, updated_at=updated_at, merge_official=False)
        if force and (breadth is None or breadth.total_amount <= 0 or not rows):
            breadth = _load_off_session_breadth(trade_date=factor_date, force=force) or breadth
        elif not force and cached is not None and cached.breadth is not None:
            breadth = cached.breadth
        elif breadth is None:
            breadth = _load_off_session_breadth(trade_date=factor_date, force=force)
        sectors = load_sector_ranks(rows)
        if not sectors and cached is not None:
            sectors = list(cached.sectors)
        data = MarketOverviewData(
            indices=indices,
            breadth=breadth,
            sectors=sectors,
            environment=environment,
        )
        store_market_overview_data(data)
        return data

    data = MarketOverviewData(
        indices=indices,
        breadth=_load_breadth(rows, updated_at=updated_at),
        sectors=load_sector_ranks(rows),
        environment=environment,
    )
    store_market_overview_data(data)
    return data


def build_overview_from_market_rows(
    rows: list[dict[str, Any]],
    *,
    updated_at: str | None = None,
    intraday: bool | None = None,
) -> tuple[MarketBreadthSnapshot | None, list[SectorRankItem]]:
    """由市场页 catalog 行增量刷新广度与行业榜（不拉指数）。

    显式 ``intraday=False`` 时仅重算广度并回退缓存行业榜；未传参时按当前是否交易时段推断，
    盘外仍会按行情行重算行业榜。
    """
    explicit_intraday = intraday is not None
    if intraday is None:
        intraday = is_ashare_trading_session()

    if not rows:
        return None, []

    if not intraday:
        breadth = _load_breadth(rows, updated_at=updated_at, merge_official=False)
        if explicit_intraday:
            peeked = peek_market_overview_data(intraday=False)
            sectors = list(peeked.sectors) if peeked is not None else []
        else:
            sectors = load_sector_ranks(rows)
            if not sectors:
                peeked = peek_market_overview_data(intraday=False)
                if peeked is not None:
                    sectors = list(peeked.sectors)
        return breadth, sectors

    return _load_breadth(rows, updated_at=updated_at), load_sector_ranks(rows)
