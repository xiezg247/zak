"""Polars 盘中资金代理（涨幅 × 成交额）。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.domain.market.quote_row import quote_row_copy
from vnpy_ashare.screener.dimensions.base import DimensionHit, dimension_hit_row, rank_score
from vnpy_ashare.screener.dimensions.moneyflow_resolve import _INTRADAY_DIMENSION_ID, _INTRADAY_LABEL
from vnpy_ashare.screener.engine.snapshot_frame import change_pct_expr, frame_to_row_dicts, snapshot_rows_to_dataframe


def hits_from_moneyflow_proxy_polars(
    rows: list[Any],
    pool_size: int,
    *,
    weight: float,
) -> list[DimensionHit]:
    df = snapshot_rows_to_dataframe(rows)
    if df.is_empty():
        return []

    change = change_pct_expr()
    amount = pl.col("amount").cast(pl.Float64, strict=False).fill_null(0.0)
    turnover = pl.col("turnover_rate").cast(pl.Float64, strict=False).fill_null(0.0)
    price = pl.coalesce(
        pl.col("last_price").cast(pl.Float64, strict=False),
        pl.col("close").cast(pl.Float64, strict=False),
    ).fill_null(0.0)

    proxy = (
        pl.when(change <= 0)
        .then(pl.lit(0.0))
        .when(amount > 0)
        .then(change * amount)
        .when((turnover > 0) & (price > 0))
        .then(change * turnover * price)
        .otherwise(pl.lit(0.0))
        .alias("_proxy_score")
    )
    ranked = (
        df.filter(pl.col("vt_symbol").cast(pl.Utf8, strict=False).fill_null("").str.len_chars() > 0)
        .with_columns(proxy)
        .filter(pl.col("_proxy_score") > 0)
        .sort("_proxy_score", descending=True, nulls_last=True)
        .head(pool_size)
    )
    if ranked.is_empty():
        return []

    hits: list[DimensionHit] = []
    total = ranked.height
    for index, item in enumerate(frame_to_row_dicts(ranked), start=1):
        vt_symbol = str(item.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        payload = quote_row_copy(item, moneyflow_proxy=True)
        amount_wan = float(item.get("amount") or 0) / 1e4
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id=_INTRADAY_DIMENSION_ID,
                label=_INTRADAY_LABEL,
                weight=weight,
                score=rank_score(index, total),
                reason=(f"盘中资金：涨幅 {float(item.get('change_pct') or 0):+.2f}% + 成交额 {amount_wan:,.0f} 万（代理），排名第 {index}"),
                row=dimension_hit_row(payload),
            )
        )
    return hits
