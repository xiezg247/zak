"""选股上下文预过滤：配方硬过滤与恐贪（与 screening_context 解耦，避免 import 环）。"""

from __future__ import annotations

from vnpy_ashare.domain.market.quote_row import coerce_quote_rows
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesSnapshot
from vnpy_ashare.screener.data.screening_context import ScreeningContext
from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.sentiment.snapshot_prefilter import apply_sentiment_snapshot_prefilter


def _replace_context_snapshot(ctx: ScreeningContext, *, rows: list, total: int | None = None) -> None:
    snapshot = getattr(ctx, "_snapshot", None)
    if snapshot is None:
        return
    ctx._snapshot = MarketQuotesSnapshot(
        rows=coerce_quote_rows(rows),
        updated_at=snapshot.updated_at,
        total=len(rows) if total is None else total,
        source=snapshot.source,
    )


def apply_recipe_prefilter_to_context(ctx: ScreeningContext) -> None:
    """将配方硬过滤（含 RECIPE_ALLOWED / ASHARE_TRADING_BOARDS）应用到上下文行情快照。"""
    snapshot = getattr(ctx, "_snapshot", None)
    if snapshot is None or not getattr(snapshot, "rows", None):
        return
    filtered = apply_recipe_filters(list(snapshot.rows))
    if len(filtered) == len(snapshot.rows):
        return
    _replace_context_snapshot(ctx, rows=filtered)


def apply_sentiment_prefilter_to_context(ctx: ScreeningContext) -> None:
    snapshot = getattr(ctx, "_snapshot", None)
    if snapshot is None or not getattr(snapshot, "rows", None):
        return
    filtered = apply_sentiment_snapshot_prefilter(list(snapshot.rows))
    if len(filtered) == len(snapshot.rows):
        return
    _replace_context_snapshot(ctx, rows=filtered)
