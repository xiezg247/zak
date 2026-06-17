"""市场页大盘概览数据加载（主要指数 + 市场广度 + 行业榜）。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel
from vnpy_ashare.domain.market.quote_row import QuoteRowLike
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.integrations.tickflow import fetch_index_ticker
from vnpy_ashare.quotes.core.quote_rows import get_market_quotes_cache
from vnpy_ashare.quotes.market.limit_ladder_summary import compute_limit_ladder_counts
from vnpy_ashare.quotes.market.market_breadth import MarketBreadthSnapshot, compute_market_breadth, merge_official_limit_counts
from vnpy_ashare.quotes.market.market_environment import MarketEnvironmentSnapshot, load_market_environment
from vnpy_ashare.quotes.market.market_summary_cache import peek_limit_ladder_counts, resolve_limit_ladder_counts
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError, load_market_quote_rows
from vnpy_ashare.screener.sector.sector_summary import attach_industry, compute_sector_distribution

SECTOR_TOP_N = 10
SECTOR_MIN_STOCKS = 3


class SectorRankItem(FrozenModel):
    industry: str = Field(description="所属行业")
    count: int = Field(description="数量")
    avg_change_pct: float = Field(description="平均涨跌幅（%）")


class MarketOverviewData(FrozenModel):
    indices: list[tuple[str, QuoteSnapshot]] = Field(description="指数列表")
    breadth: MarketBreadthSnapshot | None = Field(description="市场广度")
    sectors: list[SectorRankItem] = Field(description="行业榜")
    environment: MarketEnvironmentSnapshot | None = Field(default=None, description="大盘环境指标")
    limit_ladder_counts: dict[str, int] | None = Field(default=None, description="涨跌停梯队统计")


def _quote_rows_for_overview() -> tuple[list[QuoteRowLike], str | None]:
    cached = get_market_quotes_cache()
    if cached:
        return cached, None
    try:
        snapshot = load_market_quote_rows()
    except MarketQuotesLoadError:
        return [], None
    return snapshot.rows, snapshot.updated_at


def load_sector_ranks(rows: Sequence[QuoteRowLike], *, top_n: int = SECTOR_TOP_N) -> list[SectorRankItem]:
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


def _load_breadth(rows: Sequence[QuoteRowLike], *, updated_at: str | None) -> MarketBreadthSnapshot | None:
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
        limit_ladder_counts=resolve_limit_ladder_counts(rows, compute=compute_limit_ladder_counts),
    )


def build_overview_from_market_rows(
    rows: list[dict[str, Any]],
    *,
    updated_at: str | None = None,
    include_ladder_counts: bool = False,
) -> tuple[MarketBreadthSnapshot | None, list[SectorRankItem], dict[str, int] | None]:
    """由市场页 catalog 行增量刷新广度与行业榜（不拉指数）。

    连板梯队统计默认跳过（全市场硬过滤极慢），仅 Worker 全量刷新时开启。
    """
    if not rows:
        empty_ladder = {label: 0 for label in compute_limit_ladder_counts([])} if include_ladder_counts else None
        return None, [], empty_ladder
    breadth = _load_breadth(rows, updated_at=updated_at)
    ladder = None
    if include_ladder_counts:
        ladder = peek_limit_ladder_counts() or compute_limit_ladder_counts(rows)
    return breadth, load_sector_ranks(rows), ladder
