"""市场页大盘概览数据加载（主要指数 + 市场广度 + 行业榜）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vnpy_ashare.ai.context.store import get_market_quotes_cache
from vnpy_ashare.integrations.tickflow import fetch_index_ticker
from vnpy_ashare.quotes.market_breadth import MarketBreadthSnapshot, compute_market_breadth, merge_official_limit_counts
from vnpy_ashare.quotes.market_environment import MarketEnvironmentSnapshot, load_market_environment
from vnpy_ashare.quotes.snapshot import QuoteSnapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError, load_market_quote_rows
from vnpy_ashare.screener.sector.sector_summary import attach_industry, compute_sector_distribution

SECTOR_TOP_N = 10
SECTOR_MIN_STOCKS = 3


@dataclass(frozen=True)
class SectorRankItem:
    industry: str
    count: int
    avg_change_pct: float


@dataclass(frozen=True)
class MarketOverviewData:
    indices: list[tuple[str, QuoteSnapshot]]
    breadth: MarketBreadthSnapshot | None
    sectors: list[SectorRankItem]
    environment: MarketEnvironmentSnapshot | None = None


def _quote_rows_for_overview() -> tuple[list[dict[str, Any]], str | None]:
    cached = get_market_quotes_cache()
    if cached:
        return cached, None
    try:
        snapshot = load_market_quote_rows()
    except MarketQuotesLoadError:
        return [], None
    return snapshot.rows, snapshot.updated_at


def load_sector_ranks(rows: list[dict[str, Any]], *, top_n: int = SECTOR_TOP_N) -> list[SectorRankItem]:
    """按行业平均涨幅排序，返回 Top N。"""
    if not rows:
        return []
    enriched = attach_industry(rows)
    if not enriched:
        return []
    stats = compute_sector_distribution(enriched, top_n=top_n, min_stocks=SECTOR_MIN_STOCKS)
    return [
        SectorRankItem(
            industry=str(item["industry"]),
            count=int(item["count"]),
            avg_change_pct=float(item["avg_change_pct"]),
        )
        for item in stats
    ]


def _load_breadth(rows: list[dict[str, Any]], *, updated_at: str | None) -> MarketBreadthSnapshot | None:
    if not rows:
        return None
    breadth = compute_market_breadth(rows, updated_at=updated_at)
    return merge_official_limit_counts(breadth)


def load_market_overview() -> MarketOverviewData:
    """拉取主要指数、市场广度与行业榜。"""
    rows, updated_at = _quote_rows_for_overview()
    indices = fetch_index_ticker()
    indices.sort(key=lambda item: item[1].change_pct, reverse=True)
    return MarketOverviewData(
        indices=indices,
        breadth=_load_breadth(rows, updated_at=updated_at),
        sectors=load_sector_ranks(rows),
        environment=load_market_environment(),
    )


def build_overview_from_market_rows(
    rows: list[dict[str, Any]],
    *,
    updated_at: str | None = None,
) -> tuple[MarketBreadthSnapshot | None, list[SectorRankItem]]:
    """由市场页 catalog 行增量刷新广度与行业榜（不拉指数）。"""
    if not rows:
        return None, []
    breadth = _load_breadth(rows, updated_at=updated_at)
    return breadth, load_sector_ranks(rows)
