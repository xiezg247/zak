"""盘中配方恐贪指数权重调制（非硬过滤）。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from vnpy_ashare.config.constants.recipe import ENV_SENTIMENT_GATE
from vnpy_ashare.domain.core.env import env_or_prefs_bool
from vnpy_ashare.domain.screener.result_row import (
    ScreenerResultRow,
    coerce_screener_result_rows,
    screening_row_sort_key,
    update_screening_row,
)
from vnpy_ashare.screener.recipe_tuning_prefs import load_recipe_tuning_prefs
from vnpy_ashare.screener.sentiment.emotion_gate import apply_emotion_modulation
from vnpy_ashare.screener.sentiment.fear_greed_provider import try_fetch_fear_greed_index as _try_fetch_fear_greed_index

if TYPE_CHECKING:
    from vnpy_ashare.services.sentiment import FearGreedSnapshot


def sentiment_gate_enabled() -> bool:
    return env_or_prefs_bool(ENV_SENTIMENT_GATE, prefs=lambda: load_recipe_tuning_prefs().sentiment_gate_enabled)


def try_fetch_fear_greed_index(*, include_components: bool = False) -> FearGreedSnapshot | None:
    return _try_fetch_fear_greed_index(include_components=include_components)


def apply_sentiment_modulation(
    rows: Sequence[ScreenerResultRow],
    *,
    enabled: bool | None = None,
) -> tuple[list[ScreenerResultRow], dict[str, Any] | None]:
    """按恐贪指数微调 composite_score，恐惧时削弱追高维度、贪婪时略降换手追逐。"""
    if enabled is None:
        enabled = sentiment_gate_enabled()
    if not enabled or not rows:
        return (coerce_screener_result_rows(rows) if rows else []), None

    snapshot = try_fetch_fear_greed_index()
    meta: dict[str, Any] | None = None
    current_rows = coerce_screener_result_rows(rows)
    if snapshot is not None:
        index = float(snapshot.index)
        meta = {
            "fear_greed_index": round(index, 1),
            "fear_greed_label": snapshot.label,
        }

        tuning = load_recipe_tuning_prefs()
        updated: list[ScreenerResultRow] = []

        for row in current_rows:
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
                updates: dict[str, Any] = {
                    "composite_score": round(max(0.0, min(100.0, base + adjustment)), 1),
                }
                if note:
                    updates["sentiment_note"] = note
                updated.append(update_screening_row(row, **updates))
            else:
                updated.append(row)

        current_rows = updated

    current_rows.sort(key=screening_row_sort_key, reverse=True)
    current_rows, emotion_meta = apply_emotion_modulation(current_rows)
    if emotion_meta:
        meta = {**(meta or {}), **emotion_meta}
    return current_rows, meta
