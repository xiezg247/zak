"""盘中突破维度：昨收突破 + 接近日内高点；可选分钟 K 确认。"""

from __future__ import annotations

import os
from typing import Any

from vnpy_ashare.data.download_concurrency import run_parallel_map
from vnpy_ashare.domain.symbols import parse_tickflow_symbol
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.data.screening_context import get_volume_ratio_map
from vnpy_ashare.screener.dimensions.base import DimensionHit
from vnpy_ashare.screener.dimensions.history_signals import (
    bars_for_vt_symbol,
    breaks_rolling_high,
    load_history_bars_map,
    rolling_high_before_last,
)
from vnpy_ashare.screener.dimensions.scoring import blended_score

_META_DIMENSION_ID = "intraday_breakout"
_MIN_CHANGE_PCT = 0.5
_MIN_BREAK_PCT = 0.5
_NEAR_HIGH_RATIO = 0.99
_MIN_BREAKOUT_VOLUME_RATIO = 1.2
_MAX_PULLBACK_FROM_HIGH_PCT = 2.0
_DEFAULT_LOOKBACK_DAYS = 5


def _breakout_lookback_days() -> int:
    raw = os.getenv("BREAKOUT_LOOKBACK_DAYS", "").strip()
    if raw:
        try:
            return max(0, min(int(raw), 60))
        except ValueError:
            return _DEFAULT_LOOKBACK_DAYS
    from vnpy_ashare.screener.recipe_tuning_prefs import load_recipe_tuning_prefs

    return load_recipe_tuning_prefs().breakout_lookback_days


def run_intraday_breakout(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    ratio_map = get_volume_ratio_map()
    candidates: list[tuple[dict[str, Any], float]] = []
    for row in snapshot.rows:
        strength = _quote_breakout_strength(row, ratio_map)
        if strength is None:
            continue
        candidates.append((row, strength))

    candidates.sort(key=lambda item: item[1], reverse=True)
    lookback = _breakout_lookback_days()
    if lookback > 0 and candidates:
        candidates = _apply_rolling_high_confirm(candidates, lookback)
    if _minute_confirm_enabled():
        candidates = _apply_minute_confirm(candidates, pool_size)

    hits: list[DimensionHit] = []
    top_candidates = candidates[:pool_size]
    strength_values = [strength for _, strength in top_candidates]
    for index, (row, strength) in enumerate(top_candidates, start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        prev = float(row.get("prev_close") or 0)
        high = float(row.get("high_price") or 0)
        last = float(row.get("last_price") or 0)
        volume_ratio = _row_volume_ratio(row, ratio_map)
        ratio_note = f"，量比 {volume_ratio:.2f}" if volume_ratio is not None else ""
        lookback_note = ""
        if row.get("breakout_lookback_days"):
            lookback_note = f"，突破近 {int(row['breakout_lookback_days'])} 日高"
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id=_META_DIMENSION_ID,
                label="突破",
                weight=weight,
                score=blended_score(
                    index,
                    min(len(candidates), pool_size),
                    strength,
                    strength_values,
                ),
                reason=(f"突破：较昨收 +{strength:.2f}%，日内高 {high:.2f}（昨收 {prev:.2f}，现价 {last:.2f}{lookback_note}{ratio_note}）"),
                row=dict(row),
            )
        )
    return hits, snapshot.total


def _row_volume_ratio(row: dict[str, Any], ratio_map: dict[str, float]) -> float | None:
    ratio = float(row.get("volume_ratio") or 0)
    if ratio > 0:
        return ratio
    vt_symbol = str(row.get("vt_symbol") or "")
    mapped = ratio_map.get(vt_symbol)
    if mapped and float(mapped) > 0:
        return float(mapped)
    return None


def _quote_breakout_strength(row: dict[str, Any], ratio_map: dict[str, float]) -> float | None:
    prev = float(row.get("prev_close") or 0)
    high = float(row.get("high_price") or 0)
    last = float(row.get("last_price") or 0)
    change = float(row.get("change_pct") or 0)
    if prev <= 0 or high <= 0 or last <= 0:
        return None
    if change < _MIN_CHANGE_PCT:
        return None
    if high < prev * (1 + _MIN_BREAK_PCT / 100):
        return None
    if last < high * _NEAR_HIGH_RATIO:
        return None
    if high > 0 and (high - last) / high * 100 > _MAX_PULLBACK_FROM_HIGH_PCT:
        return None
    volume_ratio = _row_volume_ratio(row, ratio_map)
    if volume_ratio is not None and volume_ratio < _MIN_BREAKOUT_VOLUME_RATIO:
        return None
    return (last - prev) / prev * 100


def _apply_rolling_high_confirm(
    candidates: list[tuple[dict[str, Any], float]],
    lookback_days: int,
) -> list[tuple[dict[str, Any], float]]:
    vt_symbols = [str(row.get("vt_symbol") or "") for row, _ in candidates]
    bars_map = load_history_bars_map([vt for vt in vt_symbols if vt])
    if not bars_map:
        return candidates

    confirmed: list[tuple[dict[str, Any], float]] = []
    for row, strength in candidates:
        vt_symbol = str(row.get("vt_symbol") or "")
        last = float(row.get("last_price") or 0)
        bars = bars_for_vt_symbol(vt_symbol, bars_map)
        rolling_high = rolling_high_before_last(bars, lookback_days=lookback_days)
        if rolling_high is None:
            confirmed.append((row, strength))
            continue
        if breaks_rolling_high(last, rolling_high, _MIN_BREAK_PCT):
            merged = dict(row)
            merged["breakout_lookback_days"] = lookback_days
            merged["breakout_rolling_high"] = rolling_high
            confirmed.append((merged, strength))
    return confirmed if confirmed else candidates


def _minute_confirm_enabled() -> bool:
    raw = os.getenv("BREAKOUT_MINUTE_CONFIRM", "0").strip().lower()
    return raw not in ("0", "false", "no", "")


def _minute_confirm_sample() -> int:
    raw = os.getenv("BREAKOUT_MINUTE_SAMPLE", "12").strip()
    try:
        return max(0, min(int(raw), 40))
    except ValueError:
        return 12


def _apply_minute_confirm(
    candidates: list[tuple[dict[str, Any], float]],
    pool_size: int,
) -> list[tuple[dict[str, Any], float]]:
    sample = _minute_confirm_sample()
    if sample <= 0 or not candidates:
        return candidates

    probe = candidates[: max(sample, pool_size)]

    def worker(item: tuple[dict[str, Any], float]) -> tuple[dict[str, Any], float] | None:
        row, strength = item
        if _minute_bar_confirms_breakout(row):
            return item
        return None

    confirmed = run_parallel_map(probe, worker, max_workers=min(4, len(probe)))
    kept = [item for item in confirmed if item is not None]
    if kept:
        return kept
    return candidates[:pool_size]


def _minute_bar_confirms_breakout(row: dict[str, Any]) -> bool:
    vt_symbol = str(row.get("vt_symbol") or "")
    item = parse_tickflow_symbol(vt_symbol, str(row.get("name") or ""))
    if item is None:
        return True
    try:
        from vnpy_ashare.integrations.tickflow import fetch_intraday_bars

        bars = fetch_intraday_bars(item)
    except Exception:
        return True
    if len(bars) < 2:
        return True
    prev_close = float(row.get("prev_close") or 0)
    if prev_close <= 0:
        return True
    recent = bars[-3:]
    highs = [float(bar.high_price or 0) for bar in recent]
    closes = [float(bar.close_price or 0) for bar in recent]
    if not highs or not closes:
        return True
    session_high = max(highs)
    last_close = closes[-1]
    return session_high >= prev_close * (1 + _MIN_BREAK_PCT / 100) and last_close >= session_high * 0.985
