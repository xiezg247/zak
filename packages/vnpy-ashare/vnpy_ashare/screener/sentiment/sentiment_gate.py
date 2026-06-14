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

    snapshot = try_fetch_fear_greed_index()
    if snapshot is None:
        return rows, None

    index = float(snapshot.index)
    meta: dict[str, Any] = {
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
    return rows, meta
