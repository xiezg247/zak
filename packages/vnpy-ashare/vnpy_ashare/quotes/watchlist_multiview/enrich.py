"""自选多维看盘行 enrich（信号 / 持仓 / 板块）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.domain.trading.position import PositionSnapshot
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.quotes.core.quote_rows import get_market_quotes_cache
from vnpy_ashare.quotes.market.market_overview_loaders import SectorRankItem, load_sector_ranks
from vnpy_ashare.quotes.watchlist_multiview.models import WatchlistMultiRow
from vnpy_ashare.screener.data.screening_context import get_stock_industry_map

if TYPE_CHECKING:
    from collections.abc import Mapping


def _sector_rank_map(sectors: list[SectorRankItem]) -> dict[str, tuple[int, float]]:
    return {item.industry: (rank, item.avg_change_pct) for rank, item in enumerate(sectors, start=1)}


def enrich_multiview_rows(
    rows: tuple[WatchlistMultiRow, ...],
    *,
    signal_symbols: set[str] | frozenset[str] | None = None,
    signal_cache: Mapping[str, SignalSnapshot] | None = None,
    position_cache: Mapping[str, PositionSnapshot] | None = None,
    industry_map: dict[str, str] | None = None,
    sparklines: Mapping[str, tuple[float, ...]] | None = None,
    sparkline_kind: Literal["daily", "intraday", "minute", "none"] = "none",
) -> tuple[WatchlistMultiRow, ...]:
    signal_symbols = signal_symbols or frozenset()
    signal_cache = signal_cache or {}
    position_cache = position_cache or {}
    sparklines = sparklines or {}

    sectors = load_sector_ranks(get_market_quotes_cache() or [])
    sector_lookup = _sector_rank_map(sectors)

    industries = industry_map
    if industries is None:
        try:
            industries = get_stock_industry_map()
        except Exception:
            industries = {}

    enriched: list[WatchlistMultiRow] = []
    for row in rows:
        item = parse_stock_symbol(row.vt_symbol)
        ts_code = item.ts_code if item is not None else ""
        industry = (industries.get(ts_code) or "").strip() or None
        sector_rank: int | None = None
        sector_avg: float | None = None
        if industry and industry in sector_lookup:
            sector_rank, sector_avg = sector_lookup[industry]

        signal_label: str | None = None
        if row.vt_symbol in signal_symbols:
            snap = signal_cache.get(row.vt_symbol)
            if snap is not None and snap.signal_label and snap.signal != "na":
                signal_label = snap.signal_label

        has_position = row.vt_symbol in position_cache
        position_pnl_pct = None
        if has_position:
            pos = position_cache[row.vt_symbol]
            position_pnl_pct = pos.unrealized_pnl_pct

        points = sparklines.get(row.vt_symbol, row.sparkline_points)
        row_kind: Literal["daily", "intraday", "minute", "none"] = sparkline_kind if points else "none"

        enriched.append(
            row.model_copy(
                update={
                    "signal_label": signal_label,
                    "has_position": has_position,
                    "position_pnl_pct": position_pnl_pct,
                    "industry": industry,
                    "sector_rank": sector_rank,
                    "sector_avg_change": sector_avg,
                    "sparkline_points": points,
                    "sparkline_kind": row_kind,
                },
            ),
        )
    return tuple(enriched)
