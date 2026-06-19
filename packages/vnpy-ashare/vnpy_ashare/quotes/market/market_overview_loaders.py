"""市场页大盘概览数据加载（主要指数 + 市场广度 + 行业榜）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.breadth import MarketBreadthSnapshot
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.market.overview import MarketOverviewData, SectorRankItem
from vnpy_ashare.domain.market.quote_row import QuoteRowsLike
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.integrations.tickflow.quotes import fetch_index_ticker
from vnpy_ashare.integrations.tushare.factors import fetch_industry_l2_to_l1_map
from vnpy_ashare.quotes.core.quote_rows import get_market_quotes_cache
from vnpy_ashare.quotes.market.market_breadth import compute_market_breadth, merge_official_limit_counts
from vnpy_ashare.quotes.market.market_environment import load_market_environment
from vnpy_ashare.quotes.market.market_overview_cache import peek_market_overview_data, store_market_overview_data
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError, load_market_quote_rows
from vnpy_ashare.screener.sector.sector_summary import attach_industry, compute_sector_distribution

__all__ = [
    "MarketOverviewData",
    "SECTOR_MIN_STOCKS",
    "SECTOR_TOP_N",
    "SectorRankItem",
    "load_market_overview",
]

SECTOR_TOP_N = 10
SECTOR_MIN_STOCKS = 3


def _quote_rows_for_overview(*, allow_network: bool = True) -> tuple[QuoteRowsLike, str | None]:
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


def load_market_overview(*, intraday: bool = True) -> MarketOverviewData:
    """拉取主要指数、市场广度与行业榜。

    非交易时段仅读缓存或轻量指数/环境，跳过行业榜与 Tushare 涨跌停校正。
    """
    if not intraday:
        cached = peek_market_overview_data(intraday=False)
        if cached is not None:
            try:
                indices = _fetch_sorted_indices()
            except Exception:
                indices = list(cached.indices)
            data = cached.model_copy(update={"indices": indices})
            store_market_overview_data(data)
            return data

    allow_network = intraday
    rows, updated_at = _quote_rows_for_overview(allow_network=allow_network)
    indices = _fetch_sorted_indices()
    environment = load_market_environment()

    if not intraday:
        cached = peek_market_overview_data(intraday=False)
        breadth = cached.breadth if cached is not None and cached.breadth is not None else _load_breadth(rows, updated_at=updated_at, merge_official=False)
        sectors = list(cached.sectors) if cached is not None else []
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

    非交易时段跳过行业榜重算与 Tushare 涨跌停校正。
    """
    if intraday is None:
        intraday = is_ashare_trading_session()

    if not rows:
        return None, []

    if not intraday:
        breadth = _load_breadth(rows, updated_at=updated_at, merge_official=False)
        peeked = peek_market_overview_data(intraday=False)
        sectors = list(peeked.sectors) if peeked is not None else []
        return breadth, sectors

    return _load_breadth(rows, updated_at=updated_at), load_sector_ranks(rows)
