"""情绪周期门控（依赖 emotion_cycle_bridge，与 snapshot_prefilter 解耦）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.quotes.market.emotion_cycle_bridge import try_load_emotion_cycle_snapshot


def apply_emotion_modulation(
    rows: list[dict[str, Any]],
    *,
    snapshot: Any | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """按情绪周期 position_factor 缩放 composite_score；退潮期仅保留 Top3 观察。"""
    if not rows:
        return rows, None

    cycle = snapshot if snapshot is not None else try_load_emotion_cycle_snapshot()
    if cycle is None:
        return rows, None

    factor = float(cycle.position_factor)
    meta: dict[str, Any] = {
        "emotion_stage": cycle.stage,
        "emotion_stage_label": cycle.stage_label,
        "emotion_position_factor": round(factor, 3),
        "allow_new_positions": cycle.allow_new_positions,
    }

    for row in rows:
        base = float(row.get("composite_score") or 0)
        adjusted = round(max(0.0, min(100.0, base * factor)), 1)
        row["composite_score"] = adjusted
        note = f"{cycle.stage_label} 仓位系数×{factor:.2f}"
        if not cycle.allow_new_positions:
            note += "（不建议新开）"
        row["emotion_note"] = note

    if cycle.stage == "recession":
        rows.sort(
            key=lambda item: (
                float(item.get("composite_score") or 0),
                len(item.get("hit_reasons") or []),
            ),
            reverse=True,
        )
        rows = rows[:3]
        meta["emotion_capped"] = True
        meta["emotion_cap_reason"] = "退潮期仅保留 Top3 观察"

    rows.sort(
        key=lambda item: (
            float(item.get("composite_score") or 0),
            len(item.get("hit_reasons") or []),
        ),
        reverse=True,
    )
    return rows, meta


def apply_emotion_gate_only_finalize(
    rows: list[dict[str, Any]],
    *,
    top_n: int,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """R-04：冰点空池；退潮 Top3 观察；其余阶段带情绪备注。"""
    cycle = try_load_emotion_cycle_snapshot()
    if cycle is None:
        return rows[:top_n], None

    meta: dict[str, Any] = {
        "emotion_stage": cycle.stage,
        "emotion_stage_label": cycle.stage_label,
        "allow_new_positions": cycle.allow_new_positions,
    }

    if cycle.stage == "ice":
        meta["gate_message"] = f"{cycle.stage_label}·不宜新开"
        return [], meta

    if cycle.stage == "recession":
        observation = rows[: min(top_n, 3)]
        for row in observation:
            reason = str(row.get("hit_reason") or "")
            row["hit_reason"] = f"退潮观察 · {reason}" if reason else "退潮观察"
            row["emotion_note"] = cycle.stage_label
        meta["gate_message"] = "退潮期仅保留 Top3 观察"
        return observation, meta

    meta["gate_message"] = f"{cycle.stage_label}·情绪观察"
    return rows[:top_n], meta
