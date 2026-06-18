"""恐贪快照前置缩池（无 emotion_cycle 依赖）。"""

from __future__ import annotations

from vnpy_ashare.config.constants.recipe import ENV_SENTIMENT_GATE
from vnpy_ashare.domain.core.env import env_or_prefs_bool
from vnpy_ashare.domain.market.quote_row import (
    QuoteRow,
    QuoteRowsLike,
    coerce_quote_row,
    coerce_quote_rows,
)
from vnpy_ashare.screener.dimensions.momentum_bounds import momentum_change_bounds
from vnpy_ashare.screener.recipe_tuning_prefs import load_recipe_tuning_prefs
from vnpy_ashare.screener.sentiment.fear_greed_provider import try_fetch_fear_greed_index


def sentiment_gate_enabled() -> bool:
    return env_or_prefs_bool(ENV_SENTIMENT_GATE, prefs=lambda: load_recipe_tuning_prefs().sentiment_gate_enabled)


def apply_sentiment_snapshot_prefilter(rows: QuoteRowsLike) -> list[QuoteRow]:
    """恐贪前置缩池：极度恐惧时剔除涨幅过高的标的（先于维度打分）。"""
    materialized = coerce_quote_rows(rows)
    if not sentiment_gate_enabled() or not materialized:
        return materialized
    snapshot = try_fetch_fear_greed_index()
    if snapshot is None:
        return materialized
    index = float(snapshot.index)
    if index >= 45:
        return materialized

    _, max_change = momentum_change_bounds()
    if index >= 30:
        cap = max_change
    else:
        cap = min(max_change, max_change * 0.85)

    filtered: list[QuoteRow] = []
    for row in materialized:
        change = float(row.get("change_pct") or row.get("pct_chg") or 0)
        if change > cap:
            continue
        filtered.append(coerce_quote_row(row))
    return filtered if filtered else materialized
