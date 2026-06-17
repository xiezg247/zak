"""选股上下文恐贪预过滤（与 screening_context 解耦，避免 import 环）。"""

from __future__ import annotations

from vnpy_ashare.screener.data.quotes_loader import MarketQuotesSnapshot
from vnpy_ashare.screener.data.screening_context import ScreeningContext
from vnpy_ashare.screener.sentiment.snapshot_prefilter import apply_sentiment_snapshot_prefilter


def apply_sentiment_prefilter_to_context(ctx: ScreeningContext) -> None:
    snapshot = getattr(ctx, "_snapshot", None)
    if snapshot is None or not getattr(snapshot, "rows", None):
        return
    filtered = apply_sentiment_snapshot_prefilter(list(snapshot.rows))
    if len(filtered) == len(snapshot.rows):
        return
    ctx._snapshot = MarketQuotesSnapshot(
        rows=filtered,
        updated_at=snapshot.updated_at,
        total=snapshot.total,
        source=snapshot.source,
    )
