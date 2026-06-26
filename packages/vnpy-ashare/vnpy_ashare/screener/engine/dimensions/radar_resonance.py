"""Polars 雷达共振维度。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.screener.engine.snapshot_frame import frame_to_row_dicts, snapshot_rows_to_dataframe


def build_radar_resonance_rows_polars(
    entries: list[Any],
    snapshot_rows: list[Any],
    *,
    pool_size: int,
) -> list[dict[str, Any]]:
    if not entries:
        return []

    res_rows: list[dict[str, Any]] = []
    for entry in entries:
        res_rows.append(
            {
                "vt_symbol": str(entry.vt_symbol or ""),
                "resonance_score": float(entry.resonance_score or 0),
                "resonance_card_count": int(entry.card_count or 0),
                "leader_tier": str(entry.leader_tier or ""),
                "leader_score": entry.leader_score,
            }
        )
    res_df = pl.DataFrame(res_rows).filter(pl.col("vt_symbol").str.len_chars() > 0)
    if res_df.is_empty():
        return []

    snap_df = snapshot_rows_to_dataframe(snapshot_rows)
    if snap_df.is_empty() or "vt_symbol" not in snap_df.columns:
        return []

    overlap = {"resonance_score", "resonance_card_count", "leader_tier", "leader_score"}
    snap_cols = [col for col in snap_df.columns if col not in overlap]
    snap_df = snap_df.select(snap_cols)

    joined = (
        res_df.join(snap_df, on="vt_symbol", how="inner")
        .sort(["resonance_score", "resonance_card_count"], descending=[True, True])
        .head(pool_size)
    )
    if joined.is_empty():
        return []

    rows = frame_to_row_dicts(joined)
    for row in rows:
        tier = str(row.pop("leader_tier", "") or "").strip()
        if tier:
            row["leader_tier"] = tier
        score = row.pop("leader_score", None)
        if score is not None:
            row["leader_score"] = score
    return rows
