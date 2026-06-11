"""放量维度：成交量排行。"""

from __future__ import annotations

from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits
from vnpy_ashare.screener.preset.presets import SCREENER_VOLUME_SURGE
from vnpy_ashare.screener.preset.rules import apply_quote_preset


def run_volume_surge(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
        rows = apply_quote_preset(SCREENER_VOLUME_SURGE, snapshot.rows, top_n=pool_size)
        return quote_hits(
            rows,
            dimension_id="volume_surge",
            label="放量",
            weight=weight,
            reason_builder=lambda row, rank: f"放量：成交量 {float(row.get('volume') or 0):,.0f}，排名第 {rank}",
        ), snapshot.total
    except MarketQuotesLoadError:
        return [], 0
