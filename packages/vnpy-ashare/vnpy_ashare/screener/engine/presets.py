"""Polars 预设排序（change_top / turnover 等）。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import polars as pl

from vnpy_ashare.screener.engine.frame import restore_rows, rows_with_index
from vnpy_ashare.screener.data.screening_context import get_volume_ratio_map
from vnpy_ashare.screener.preset.presets import (
    SCREENER_CHANGE_TOP,
    SCREENER_CUSTOM,
    SCREENER_STRONG_UP,
    SCREENER_TURNOVER,
    SCREENER_VOLUME_RATIO,
    SCREENER_VOLUME_SURGE,
)
from vnpy_ashare.screener.preset.rules import STRONG_UP_MIN_CHANGE_PCT


def _ensure_sort_columns(df: pl.DataFrame) -> pl.DataFrame:
    missing = [name for name in ("change_pct", "turnover_rate", "volume", "amount", "total_mv", "circ_mv", "volume_ratio", "vt_symbol") if name not in df.columns]
    if not missing:
        return df
    return df.with_columns(pl.lit(None).alias(name) for name in missing)


def sort_quote_rows_polars(
    rows: Sequence[Any],
    *,
    preset: str,
    top_n: int,
    min_change_pct: float | None = None,
    max_change_pct: float | None = None,
    min_turnover: float | None = None,
) -> list[Any]:
    if not rows:
        return []

    payloads, _ = rows_with_index(rows)
    df = pl.DataFrame(payloads, infer_schema_length=max(len(payloads), 1))
    df = _ensure_sort_columns(df)
    preset = preset.strip()
    top_n = max(1, min(int(top_n or 20), 200))

    if preset == SCREENER_CHANGE_TOP:
        sorted_df = df.sort("change_pct", descending=True, nulls_last=True)
    elif preset == SCREENER_CUSTOM:
        sorted_df = df.sort("change_pct", descending=True, nulls_last=True)
    elif preset == SCREENER_STRONG_UP:
        sorted_df = df.filter(pl.col("change_pct").cast(pl.Float64, strict=False).fill_null(0.0) >= STRONG_UP_MIN_CHANGE_PCT).sort(
            "change_pct",
            descending=True,
            nulls_last=True,
        )
    elif preset == SCREENER_TURNOVER:
        sorted_df = df.sort("turnover_rate", descending=True, nulls_last=True)
    elif preset == SCREENER_VOLUME_RATIO:
        ratio_map = get_volume_ratio_map()
        if ratio_map:
            map_df = pl.DataFrame(
                {"vt_symbol": list(ratio_map.keys()), "_map_ratio": list(ratio_map.values())},
            )
            df = df.join(map_df, on="vt_symbol", how="left")
            df = df.with_columns(
                pl.coalesce(
                    pl.col("_map_ratio").cast(pl.Float64, strict=False),
                    pl.col("volume_ratio").cast(pl.Float64, strict=False),
                    pl.lit(0.0),
                ).alias("_volume_ratio")
            )
        else:
            df = df.with_columns(pl.col("volume_ratio").cast(pl.Float64, strict=False).fill_null(0.0).alias("_volume_ratio"))
        sorted_df = df.filter(pl.col("_volume_ratio") > 0).sort("_volume_ratio", descending=True, nulls_last=True)
    elif preset == SCREENER_VOLUME_SURGE:
        sorted_df = df.with_columns(
            pl.max_horizontal(
                pl.col("volume").cast(pl.Float64, strict=False).fill_null(0.0),
                pl.col("amount").cast(pl.Float64, strict=False).fill_null(0.0),
                pl.col("total_mv").cast(pl.Float64, strict=False).fill_null(0.0),
                pl.col("circ_mv").cast(pl.Float64, strict=False).fill_null(0.0),
                pl.col("turnover_rate").cast(pl.Float64, strict=False).fill_null(0.0),
            ).alias("_liq")
        ).sort("_liq", descending=True, nulls_last=True)
    else:
        sorted_df = df

    if min_change_pct is not None:
        sorted_df = sorted_df.filter(pl.col("change_pct").cast(pl.Float64, strict=False).fill_null(0.0) >= min_change_pct)
    if max_change_pct is not None:
        sorted_df = sorted_df.filter(pl.col("change_pct").cast(pl.Float64, strict=False).fill_null(0.0) <= max_change_pct)
    if min_turnover is not None:
        sorted_df = sorted_df.filter(pl.col("turnover_rate").cast(pl.Float64, strict=False).fill_null(0.0) >= min_turnover)

    head = sorted_df.head(top_n).to_dicts()
    restored = restore_rows(rows, head)
    return restored
