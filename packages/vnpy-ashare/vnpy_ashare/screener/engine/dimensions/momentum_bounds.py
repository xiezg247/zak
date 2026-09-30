"""动量涨跌幅上下界（供动量维度与恐贪预过滤共用）。"""

from __future__ import annotations

import os

from vnpy_ashare.screener.recipe_tuning_prefs import load_recipe_tuning_prefs
from vnpy_ashare.screener.sentiment.fear_greed_provider import try_fetch_fear_greed_index


def momentum_change_bounds() -> tuple[float, float]:
    prefs = load_recipe_tuning_prefs()
    min_raw = os.getenv("MOMENTUM_MIN_CHANGE_PCT", "").strip()
    max_raw = os.getenv("MOMENTUM_MAX_CHANGE_PCT", "").strip()
    fear_max_raw = os.getenv("MOMENTUM_FEAR_MAX_CHANGE_PCT", "").strip()

    min_change = float(min_raw) if min_raw else prefs.momentum_min_change_pct
    max_change = float(max_raw) if max_raw else prefs.momentum_max_change_pct
    fear_max = float(fear_max_raw) if fear_max_raw else prefs.momentum_fear_max_change_pct

    snapshot = try_fetch_fear_greed_index()
    if snapshot is not None and float(snapshot.index) < 30:
        max_change = min(max_change, fear_max)
    return min_change, max_change
