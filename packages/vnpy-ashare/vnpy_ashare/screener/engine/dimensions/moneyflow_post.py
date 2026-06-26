"""Polars 盘后资金流排序（tier + streak 批量）。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.screener.engine.dimensions.moneyflow_in import apply_moneyflow_in_polars
from vnpy_ashare.screener.engine.dimensions.moneyflow_streak import build_positive_moneyflow_streak_map
from vnpy_ashare.screener.engine.snapshot_frame import frame_to_row_dicts
from vnpy_ashare.screener.preset.rules import _moneyflow_row


def rank_moneyflow_by_tier_polars(rows: list[QuoteRow], *, pool_size: int) -> list[QuoteRow]:
    """特大单净流入优先，与 ``_tier_net_amount`` 对齐。"""
    if not rows:
        return []
    df = pl.DataFrame([dict(row) for row in rows], infer_schema_length=max(len(rows), 1))
    buy_elg = pl.col("buy_elg_amount").cast(pl.Float64, strict=False).fill_null(0.0)
    sell_elg = pl.col("sell_elg_amount").cast(pl.Float64, strict=False).fill_null(0.0)
    elg = buy_elg - sell_elg
    net = pl.col("net_mf_amount").cast(pl.Float64, strict=False).fill_null(0.0)
    tier = pl.when(elg != 0).then(elg).otherwise(net)
    ranked = (
        df.with_columns(tier.alias("_tier"))
        .sort("_tier", descending=True, nulls_last=True)
        .head(max(1, pool_size))
    )
    return [_moneyflow_row(item) for item in frame_to_row_dicts(ranked)]


def rank_post_close_moneyflow_rows_polars(raw_rows: list[Any], *, pool_size: int) -> list[QuoteRow]:
    """硬过滤 + 净流入 Top 池 → tier 精排。"""
    candidates = apply_moneyflow_in_polars(raw_rows, top_n=max(pool_size * 2, pool_size))
    return rank_moneyflow_by_tier_polars(candidates, pool_size=pool_size)


def post_close_streak_map_for_rows(rows: list[QuoteRow], *, max_days: int = 5) -> dict[str, int]:
    vt_symbols = {str(row.get("vt_symbol") or "").strip() for row in rows}
    vt_symbols.discard("")
    return build_positive_moneyflow_streak_map(vt_symbols, max_days=max_days)
