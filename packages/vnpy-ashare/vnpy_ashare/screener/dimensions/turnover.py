"""换手维度：换手率排行。"""

from __future__ import annotations

from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits
from vnpy_ashare.screener.preset.presets import SCREENER_TURNOVER
from vnpy_ashare.screener.preset.rules import apply_quote_preset


def run_turnover(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
        rows = apply_quote_preset(SCREENER_TURNOVER, snapshot.rows, top_n=pool_size)
        return quote_hits(
            rows,
            dimension_id="turnover",
            label="换手",
            weight=weight,
            reason_builder=lambda row, rank: f"换手：{float(row.get('turnover_rate') or 0):.2f}%，排名第 {rank}",
        ), snapshot.total
    except MarketQuotesLoadError:
        return [], 0
