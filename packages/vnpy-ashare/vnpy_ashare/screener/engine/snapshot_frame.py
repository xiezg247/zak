"""全市场行情快照 ↔ Polars DataFrame。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import polars as pl

from vnpy_ashare.domain.symbols.stock import vt_symbol_to_ts_code
from vnpy_ashare.screener.engine.frame import row_to_dict


def _join_str_map(df: pl.DataFrame, key_col: str, mapping: dict[str, str], value_col: str) -> pl.DataFrame:
    if not mapping:
        return df.with_columns(pl.lit(None).cast(pl.Utf8).alias(value_col))
    map_df = pl.DataFrame({"_map_key": list(mapping.keys()), value_col: list(mapping.values())})
    return df.join(map_df, left_on=key_col, right_on="_map_key", how="left")


def snapshot_rows_to_dataframe(rows: Sequence[Any]) -> pl.DataFrame:
    """将行情快照行转为 DataFrame（保留 vt_symbol 等选股字段）。"""
    if not rows:
        return pl.DataFrame()
    payloads = [row_to_dict(row) for row in rows]
    df = pl.DataFrame(payloads, infer_schema_length=max(len(payloads), 1))
    # 确保 change_pct / pct_chg 均存在且无 null，防止下游 QuoteRow 校验失败
    for col, other in (("change_pct", "pct_chg"), ("pct_chg", "change_pct")):
        if col in df.columns:
            df = df.with_columns(pl.col(col).fill_null(0.0))
        elif other in df.columns:
            df = df.with_columns(pl.col(other).fill_null(0.0).alias(col))
        else:
            df = df.with_columns(pl.lit(0.0).alias(col))
    return df


def attach_industry_columns(
    df: pl.DataFrame,
    *,
    industry_map: Mapping[str, str],
    industry_l1_map: Mapping[str, str] | None = None,
    drop_unmapped: bool = True,
) -> pl.DataFrame:
    """附加 industry / industry_l1；默认丢弃无行业映射的行（对齐 attach_industry）。"""
    if df.is_empty():
        return df
    if "vt_symbol" not in df.columns:
        return pl.DataFrame() if drop_unmapped else df

    frame = df.with_columns(
        pl.col("vt_symbol")
        .cast(pl.Utf8, strict=False)
        .fill_null("")
        .map_elements(lambda vt: vt_symbol_to_ts_code(str(vt or "")) or "", return_dtype=pl.Utf8)
        .alias("_ts_code")
    )
    frame = _join_str_map(frame, "_ts_code", dict(industry_map), "industry")
    l1_map = dict(industry_l1_map or {})
    frame = _join_str_map(frame, "_ts_code", l1_map, "industry_l1")
    frame = frame.with_columns(
        pl.col("industry").cast(pl.Utf8, strict=False).fill_null("").alias("industry"),
        pl.col("industry_l1").cast(pl.Utf8, strict=False).fill_null("").alias("industry_l1"),
    )
    if not drop_unmapped:
        return frame.drop("_ts_code", strict=False)
    return frame.filter((pl.col("industry").str.len_chars() > 0) | (pl.col("industry_l1").str.len_chars() > 0)).drop(
        "_ts_code",
        strict=False,
    )


def change_pct_expr() -> pl.Expr:
    return pl.coalesce(
        pl.col("change_pct").cast(pl.Float64, strict=False),
        pl.col("pct_chg").cast(pl.Float64, strict=False),
    ).fill_null(0.0)


def frame_to_row_dicts(df: pl.DataFrame) -> list[dict[str, Any]]:
    """DataFrame → dict 行（去掉内部列）。"""
    internal = {"_ts_code", "_row_idx", "_map_key", "_ind_avg", "_liq", "_volume_ratio", "_map_ratio", "_hit_count"}
    rows: list[dict[str, Any]] = []
    for item in df.to_dicts():
        rows.append({key: value for key, value in item.items() if key not in internal})
    return rows
