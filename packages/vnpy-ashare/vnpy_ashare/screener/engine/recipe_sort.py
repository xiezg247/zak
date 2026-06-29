"""Recipe 合并结果 Polars 排序。"""

from __future__ import annotations

from typing import Any

import polars as pl


def sort_recipe_payloads_polars(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 composite_score、命中维度数降序排列 recipe 合并行。"""
    if not rows:
        return []

    df = pl.DataFrame(rows, infer_schema_length=max(len(rows), 1))
    if "composite_score" not in df.columns:
        return rows

    if "hit_reasons" in df.columns:
        hit_count = pl.col("hit_reasons").list.len()
    else:
        hit_count = pl.lit(0)

    sorted_df = df.with_columns(hit_count.alias("_hit_count")).sort(
        ["composite_score", "_hit_count"],
        descending=[True, True],
        nulls_last=True,
    )
    return sorted_df.drop("_hit_count", strict=False).to_dicts()
