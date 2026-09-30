"""雷达共振 / 龙头维度 Polars 与 hit 组装。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.quotes.radar.radar_leader import leader_tier_label
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits
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


def resonance_reason(row: dict[str, Any], rank: int) -> str:
    cards = int(row.get("resonance_card_count") or 0)
    score = float(row.get("resonance_score") or 0)
    name = str(row.get("name") or row.get("symbol") or "")
    return f"共振：{name} {cards}卡·{score:.1f}分，排名第 {rank}"


def leader_score_reason(row: dict[str, Any], rank: int) -> str:
    score = float(row.get("leader_score") or 0)
    tier = leader_tier_label(str(row.get("leader_tier") or ""))
    tier_text = f"{tier} " if tier else ""
    industry = str(row.get("industry") or "—")
    return f"龙头：{tier_text}{industry} 评分 {score:.1f}，排名第 {rank}"


def run_radar_resonance(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.data.radar_dimension_data import build_radar_resonance_dimension_rows

    rows, total = build_radar_resonance_dimension_rows(pool_size)
    if not rows:
        return [], total
    return quote_hits(
        rows,
        dimension_id="radar_resonance",
        label="共振",
        weight=weight,
        reason_builder=resonance_reason,
        metric_key="resonance_score",
    ), total


def run_leader_score(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.data.radar_dimension_data import build_leader_score_dimension_rows

    rows, total = build_leader_score_dimension_rows(pool_size)
    if not rows:
        return [], total
    return quote_hits(
        rows,
        dimension_id="leader_score",
        label="龙头",
        weight=weight,
        reason_builder=leader_score_reason,
        metric_key="leader_score",
    ), total
