"""盘中配方恐贪指数权重调制（非硬过滤）。"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vnpy_ashare.services.sentiment_service import FearGreedSnapshot


def sentiment_gate_enabled() -> bool:
    raw = os.getenv("RECIPE_SENTIMENT_GATE", "").strip()
    if raw:
        return raw.lower() not in ("0", "false", "no")
    from vnpy_ashare.screener.recipe_tuning_prefs import load_recipe_tuning_prefs

    return load_recipe_tuning_prefs().sentiment_gate_enabled


def try_fetch_fear_greed_index(*, include_components: bool = False) -> FearGreedSnapshot | None:
    """无 MainEngine 时独立计算恐贪指数；失败返回 None。"""
    try:
        from vnpy_ashare.services.sentiment_service import SentimentService

        svc = SentimentService.__new__(SentimentService)
        svc._cache = {}
        return SentimentService.compute_fear_greed(svc, include_components=include_components)
    except Exception:
        return None


def try_load_emotion_cycle_snapshot():
    try:
        from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot

        return load_emotion_cycle_snapshot()
    except Exception:
        return None


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


def apply_sentiment_modulation(
    rows: list[dict[str, Any]],
    *,
    enabled: bool | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """按恐贪指数微调 composite_score，恐惧时削弱追高维度、贪婪时略降换手追逐。"""
    if enabled is None:
        enabled = sentiment_gate_enabled()
    if not enabled or not rows:
        return rows, None

    if not enabled or not rows:
        return rows, None

    snapshot = try_fetch_fear_greed_index()
    meta: dict[str, Any] | None = None
    if snapshot is not None:
        index = float(snapshot.index)
        meta = {
            "fear_greed_index": round(index, 1),
            "fear_greed_label": snapshot.label,
        }

        from vnpy_ashare.screener.recipe_tuning_prefs import load_recipe_tuning_prefs

        tuning = load_recipe_tuning_prefs()

        for row in rows:
            dims = row.get("dimensions") or {}
            base = float(row.get("composite_score") or 0)
            adjustment = 0.0
            note = ""

            if index < 30:
                adjustment -= float(dims.get("momentum") or 0) * tuning.extreme_fear_momentum
                adjustment -= float(dims.get("sector_strength") or 0) * tuning.extreme_fear_sector
                adjustment -= float(dims.get("intraday_breakout") or 0) * tuning.extreme_fear_breakout
                note = f"极度恐惧({index:.0f}) 削弱追高维度"
            elif index < 45:
                adjustment -= float(dims.get("momentum") or 0) * tuning.fear_momentum
                note = f"恐惧({index:.0f}) 动量略降"
            elif index > 75:
                adjustment -= float(dims.get("turnover") or 0) * tuning.extreme_greed_turnover
                adjustment -= float(dims.get("volume_surge") or 0) * tuning.extreme_greed_volume_surge
                note = f"极度贪婪({index:.0f}) 换手/放量略降"
            elif index > 60:
                adjustment -= float(dims.get("turnover") or 0) * tuning.greed_turnover
                note = f"贪婪({index:.0f}) 换手略降"

            if adjustment != 0.0:
                row["composite_score"] = round(max(0.0, min(100.0, base + adjustment)), 1)
                if note:
                    row["sentiment_note"] = note

    rows.sort(
        key=lambda item: (
            float(item.get("composite_score") or 0),
            len(item.get("hit_reasons") or []),
        ),
        reverse=True,
    )
    rows, emotion_meta = apply_emotion_modulation(rows)
    if emotion_meta:
        meta = {**(meta or {}), **emotion_meta}
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


def apply_sentiment_snapshot_prefilter(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """恐贪前置缩池：极度恐惧时剔除涨幅过高的标的（先于维度打分）。"""
    if not sentiment_gate_enabled() or not rows:
        return rows
    snapshot = try_fetch_fear_greed_index()
    if snapshot is None:
        return rows
    index = float(snapshot.index)
    if index >= 45:
        return rows

    from vnpy_ashare.screener.dimensions.momentum import _momentum_change_bounds

    _, max_change = _momentum_change_bounds()
    if index >= 30:
        cap = max_change
    else:
        cap = min(max_change, max_change * 0.85)

    filtered: list[dict[str, Any]] = []
    for row in rows:
        change = float(row.get("change_pct") or row.get("pct_chg") or 0)
        if change > cap:
            continue
        filtered.append(row)
    return filtered if filtered else rows
