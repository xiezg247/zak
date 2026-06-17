"""情绪周期门控（依赖 emotion_cycle_bridge，与 snapshot_prefilter 解耦）。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from vnpy_ashare.domain.screener.result_row import (
    ScreenerResultRow,
    coerce_screener_result_rows,
    screening_row_sort_key,
    update_screening_row,
)
from vnpy_ashare.quotes.market.emotion_cycle_bridge import try_load_emotion_cycle_snapshot


def apply_emotion_modulation(
    rows: Sequence[ScreenerResultRow],
    *,
    snapshot: Any | None = None,
) -> tuple[list[ScreenerResultRow], dict[str, Any] | None]:
    """按情绪周期 position_factor 缩放 composite_score；退潮期仅保留 Top3 观察。"""
    if not rows:
        return [], None

    cycle = snapshot if snapshot is not None else try_load_emotion_cycle_snapshot()
    if cycle is None:
        return coerce_screener_result_rows(rows), None

    factor = float(cycle.position_factor)
    meta: dict[str, Any] = {
        "emotion_stage": cycle.stage,
        "emotion_stage_label": cycle.stage_label,
        "emotion_position_factor": round(factor, 3),
        "allow_new_positions": cycle.allow_new_positions,
    }

    updated: list[ScreenerResultRow] = []
    for row in coerce_screener_result_rows(rows):
        base = float(row.get("composite_score") or 0)
        adjusted = round(max(0.0, min(100.0, base * factor)), 1)
        note = f"{cycle.stage_label} 仓位系数×{factor:.2f}"
        if not cycle.allow_new_positions:
            note += "（不建议新开）"
        updated.append(update_screening_row(row, composite_score=adjusted, emotion_note=note))

    if cycle.stage == "recession":
        updated.sort(key=screening_row_sort_key, reverse=True)
        updated = updated[:3]
        meta["emotion_capped"] = True
        meta["emotion_cap_reason"] = "退潮期仅保留 Top3 观察"

    updated.sort(key=screening_row_sort_key, reverse=True)
    return updated, meta


def apply_emotion_gate_only_finalize(
    rows: Sequence[ScreenerResultRow],
    *,
    top_n: int,
) -> tuple[list[ScreenerResultRow], dict[str, Any] | None]:
    """R-04：冰点空池；退潮 Top3 观察；其余阶段带情绪备注。"""
    normalized = coerce_screener_result_rows(rows)
    cycle = try_load_emotion_cycle_snapshot()
    if cycle is None:
        return normalized[:top_n], None

    meta: dict[str, Any] = {
        "emotion_stage": cycle.stage,
        "emotion_stage_label": cycle.stage_label,
        "allow_new_positions": cycle.allow_new_positions,
    }

    if cycle.stage == "ice":
        meta["gate_message"] = f"{cycle.stage_label}·不宜新开"
        return [], meta

    if cycle.stage == "recession":
        observation = normalized[: min(top_n, 3)]
        capped: list[ScreenerResultRow] = []
        for row in observation:
            reason = str(row.get("hit_reason") or "")
            hit_reason = f"退潮观察 · {reason}" if reason else "退潮观察"
            capped.append(update_screening_row(row, hit_reason=hit_reason, emotion_note=cycle.stage_label))
        meta["gate_message"] = "退潮期仅保留 Top3 观察"
        return capped, meta

    meta["gate_message"] = f"{cycle.stage_label}·情绪观察"
    return normalized[:top_n], meta
