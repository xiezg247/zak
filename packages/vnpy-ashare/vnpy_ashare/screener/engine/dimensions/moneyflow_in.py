"""Polars 主力净流入筛选。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.screener.engine.frame import row_to_dict
from vnpy_ashare.screener.engine.snapshot_frame import frame_to_row_dicts
from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.preset.rules import _moneyflow_row


def apply_moneyflow_in_polars(rows: list[Any], *, top_n: int) -> list[QuoteRow]:
    """主力净流入 > 0 降序取 top_n（硬过滤后）。"""
    if not rows:
        return []

    filtered = apply_recipe_filters([row_to_dict(row) for row in rows])
    if not filtered:
        return []

    df = pl.DataFrame(filtered, infer_schema_length=max(len(filtered), 1))
    net = pl.col("net_mf_amount").cast(pl.Float64, strict=False).fill_null(0.0)
    df = df.filter(net > 0).sort("net_mf_amount", descending=True, nulls_last=True).head(max(1, top_n))
    return [_moneyflow_row(item) for item in frame_to_row_dicts(df)]
