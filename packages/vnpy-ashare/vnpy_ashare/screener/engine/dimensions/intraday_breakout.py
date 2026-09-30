"""盘中突破：Polars 候选评分 + 回看/分钟确认 + hit 组装。"""

from __future__ import annotations

import os
from typing import Any

import polars as pl

from vnpy_ashare.data.download_concurrency import run_parallel_map
from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowLike, coerce_quote_row, quote_row_copy
from vnpy_ashare.domain.symbols.stock import parse_tickflow_symbol
from vnpy_ashare.integrations.tickflow.klines import fetch_intraday_bars
from vnpy_ashare.screener.data.screening_context import get_volume_ratio_map
from vnpy_ashare.domain.screener.dimension_hit import DimensionHit, dimension_hit_row
from vnpy_ashare.screener.engine.dimensions.history_signals import (
    bars_for_vt_symbol,
    breaks_rolling_high,
    load_history_bars_map,
    rolling_high_before_last,
)
from vnpy_ashare.screener.engine.dimensions.scoring import blended_score
from vnpy_ashare.screener.engine.snapshot_frame import change_pct_expr, frame_to_row_dicts, snapshot_rows_to_dataframe
from vnpy_ashare.screener.recipe_tuning_prefs import load_recipe_tuning_prefs

_META_DIMENSION_ID = "intraday_breakout"
_DEFAULT_LOOKBACK_DAYS = 5
_MIN_CHANGE_PCT = 0.5
_MIN_BREAK_PCT = 0.5
_NEAR_HIGH_RATIO = 0.99
_MIN_BREAKOUT_VOLUME_RATIO = 1.2
_MAX_PULLBACK_FROM_HIGH_PCT = 2.0


def breakout_lookback_days() -> int:
    raw = os.getenv("BREAKOUT_LOOKBACK_DAYS", "").strip()
    if raw:
        try:
            return max(0, min(int(raw), 60))
        except ValueError:
            return _DEFAULT_LOOKBACK_DAYS
    return load_recipe_tuning_prefs().breakout_lookback_days


def minute_confirm_enabled() -> bool:
    raw = os.getenv("BREAKOUT_MINUTE_CONFIRM", "0").strip().lower()
    return raw not in ("0", "false", "no", "")


def score_breakout_candidates_polars(rows: list[Any]) -> list[tuple[QuoteRow, float]]:
    ratio_map = get_volume_ratio_map()
    df = snapshot_rows_to_dataframe(rows)
    if df.is_empty():
        return []

    if ratio_map:
        map_df = pl.DataFrame({"vt_symbol": list(ratio_map.keys()), "_map_ratio": list(ratio_map.values())})
        df = df.join(map_df, on="vt_symbol", how="left")
    else:
        df = df.with_columns(pl.lit(None).cast(pl.Float64).alias("_map_ratio"))

    prev = (
        pl.col("prev_close").cast(pl.Float64, strict=False).fill_null(0.0)
        if "prev_close" in df.columns
        else pl.lit(0.0)
    )
    high_exprs = [
        pl.col(name).cast(pl.Float64, strict=False)
        for name in ("high_price", "high")
        if name in df.columns
    ]
    high = pl.coalesce(*high_exprs).fill_null(0.0) if high_exprs else pl.lit(0.0)
    last_exprs = [
        pl.col(name).cast(pl.Float64, strict=False)
        for name in ("last_price", "close")
        if name in df.columns
    ]
    last = pl.coalesce(*last_exprs).fill_null(0.0) if last_exprs else pl.lit(0.0)
    change = change_pct_expr()
    row_ratio = (
        pl.col("volume_ratio").cast(pl.Float64, strict=False).fill_null(0.0)
        if "volume_ratio" in df.columns
        else pl.lit(0.0)
    )
    map_ratio = pl.col("_map_ratio").cast(pl.Float64, strict=False).fill_null(0.0)
    volume_ratio = pl.max_horizontal(row_ratio, map_ratio)
    has_ratio = volume_ratio > 0

    df = df.with_columns(
        pl.when((prev > 0) & (high > 0) & (last > 0)).then((last - prev) / prev * 100.0).otherwise(None).alias("_strength"),
        pl.when(high > 0).then((high - last) / high * 100.0).otherwise(pl.lit(999.0)).alias("_pullback_pct"),
        volume_ratio.alias("_volume_ratio"),
        has_ratio.alias("_has_ratio"),
        change.alias("_change"),
        prev.alias("_prev"),
        high.alias("_high"),
        last.alias("_last"),
    )
    df = df.filter(
        (pl.col("_prev") > 0)
        & (pl.col("_high") > 0)
        & (pl.col("_last") > 0)
        & (pl.col("_change") >= _MIN_CHANGE_PCT)
        & (pl.col("_high") >= pl.col("_prev") * (1.0 + _MIN_BREAK_PCT / 100.0))
        & (pl.col("_last") >= pl.col("_high") * _NEAR_HIGH_RATIO)
        & (pl.col("_pullback_pct") <= _MAX_PULLBACK_FROM_HIGH_PCT)
        & (~pl.col("_has_ratio") | (pl.col("_volume_ratio") >= _MIN_BREAKOUT_VOLUME_RATIO))
        & pl.col("_strength").is_not_null()
    ).sort("_strength", descending=True, nulls_last=True)

    scored: list[tuple[QuoteRow, float]] = []
    for item in frame_to_row_dicts(df):
        strength = float(item.get("_strength") or 0)
        if strength <= 0:
            continue
        scored.append((coerce_quote_row(item), strength))
    return scored


def quote_breakout_strength(row: QuoteRowLike, ratio_map: dict[str, float]) -> float | None:
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


def run_intraday_breakout_pipeline(
    rows: list[Any],
    total: int,
    pool_size: int,
    *,
    weight: float,
) -> tuple[list[DimensionHit], int]:
    ratio_map = get_volume_ratio_map()
    candidates = score_breakout_candidates_polars(rows)

    lookback = breakout_lookback_days()
    if lookback > 0 and candidates:
        candidates = _apply_rolling_high_confirm(candidates, lookback)
    if minute_confirm_enabled():
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
            lookback_note = f"，突破近 {int(row.get('breakout_lookback_days') or 0)} 日高"
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
                row=dimension_hit_row(coerce_quote_row(row)),
            )
        )
    return hits, total


def _row_volume_ratio(row: QuoteRowLike, ratio_map: dict[str, float]) -> float | None:
    ratio = float(row.get("volume_ratio") or 0)
    if ratio > 0:
        return ratio
    vt_symbol = str(row.get("vt_symbol") or "")
    mapped = ratio_map.get(vt_symbol)
    if mapped and float(mapped) > 0:
        return float(mapped)
    return None


def _apply_rolling_high_confirm(
    candidates: list[tuple[QuoteRow, float]],
    lookback_days: int,
) -> list[tuple[QuoteRow, float]]:
    vt_symbols = [str(row.get("vt_symbol") or "") for row, _ in candidates]
    bars_map = load_history_bars_map([vt for vt in vt_symbols if vt])
    if not bars_map:
        return candidates

    confirmed: list[tuple[QuoteRow, float]] = []
    for row, strength in candidates:
        vt_symbol = str(row.get("vt_symbol") or "")
        last = float(row.get("last_price") or 0)
        bars = bars_for_vt_symbol(vt_symbol, bars_map)
        rolling_high = rolling_high_before_last(bars, lookback_days=lookback_days)
        if rolling_high is None:
            confirmed.append((row, strength))
            continue
        if breaks_rolling_high(last, rolling_high, _MIN_BREAK_PCT):
            confirmed.append(
                (
                    quote_row_copy(
                        row,
                        breakout_lookback_days=lookback_days,
                        breakout_rolling_high=rolling_high,
                    ),
                    strength,
                )
            )
    return confirmed if confirmed else candidates


def _minute_confirm_sample() -> int:
    raw = os.getenv("BREAKOUT_MINUTE_SAMPLE", "12").strip()
    try:
        return max(0, min(int(raw), 40))
    except ValueError:
        return 12


def _apply_minute_confirm(
    candidates: list[tuple[QuoteRow, float]],
    pool_size: int,
) -> list[tuple[QuoteRow, float]]:
    sample = _minute_confirm_sample()
    if sample <= 0 or not candidates:
        return candidates

    probe = candidates[: max(sample, pool_size)]

    def worker(item: tuple[QuoteRow, float]) -> tuple[QuoteRow, float] | None:
        row, strength = item
        if _minute_bar_confirms_breakout(row):
            return coerce_quote_row(row), strength
        return None

    confirmed = run_parallel_map(probe, worker, max_workers=min(4, len(probe)))
    kept: list[tuple[QuoteRow, float]] = [item for item in confirmed if item is not None]
    if kept:
        return kept
    return candidates[:pool_size]


def _minute_bar_confirms_breakout(row: QuoteRowLike) -> bool:
    vt_symbol = str(row.get("vt_symbol") or "")
    item = parse_tickflow_symbol(vt_symbol, str(row.get("name") or ""))
    if item is None:
        return True
    try:
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
