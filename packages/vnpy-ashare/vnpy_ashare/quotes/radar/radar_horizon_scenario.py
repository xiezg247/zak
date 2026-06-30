"""雷达未来·情景：轻量动能/波动打分（非确定性预测）。"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from vnpy_ashare.data.bar_access import load_scope_bars
from vnpy_ashare.data.download_concurrency import run_parallel_map
from vnpy_ashare.data.pattern_bars import pattern_load_max_workers
from vnpy_ashare.domain.radar.scenario import ScenarioMetrics
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot, signal_is_fresh, signal_missing_kline
from vnpy_ashare.quotes.radar.radar_horizon_rules import _has_near_unlock, last_price_for_snapshot
from vnpy_ashare.quotes.radar.radar_models import RadarRow, merge_row_quotes

# 日K加载起始偏移：25 根用于波动率计算，60 交易日 ≈ 90 天
_BAR_START_LOOKBACK = timedelta(days=90)

SCENARIO_VARIANTS: frozenset[str] = frozenset(
    {"scenario_bull", "scenario_volatile", "scenario_bear"},
)

HORIZON_DAYS = 5
MIN_DAILY_VOL_PCT = 2.0
MIN_BULL_SCORE = 38.0
MIN_BEAR_SCORE = 38.0
MIN_VOLATILITY_SCORE = 4.5

SCENARIO_VARIANT_LABELS: dict[str, str] = {
    "scenario_bull": "偏多",
    "scenario_volatile": "高波动",
    "scenario_bear": "偏空",
}


def _estimate_bar_stats(
    vt_symbol: str,
    *,
    horizon_days: int = HORIZON_DAYS,
) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return None, None, None, None, None
    bars = load_scope_bars(
        item.symbol,
        item.exchange,
        "daily",
        datetime.now() - _BAR_START_LOOKBACK,
        datetime.now(),
    )
    if len(bars) < 12:
        return None, None, None, None, None
    closes = [float(bar.close_price) for bar in bars[-25:]]
    last_close = closes[-1]
    momentum_pct = None
    if len(closes) >= 6 and closes[-6] > 0:
        momentum_pct = round((last_close - closes[-6]) / closes[-6] * 100, 2)
    returns: list[float] = []
    for index in range(1, len(closes)):
        prev = closes[index - 1]
        if prev <= 0:
            continue
        returns.append((closes[index] - prev) / prev)
    if len(returns) < 5:
        return momentum_pct, None, None, None, None
    tail = returns[-20:]
    mean_ret = sum(tail) / len(tail)
    variance = sum((value - mean_ret) ** 2 for value in tail) / len(tail)
    daily_vol_pct = round(math.sqrt(variance) * 100, 2)
    band_move_pct = round(daily_vol_pct * math.sqrt(max(1, horizon_days)), 2)
    band_lower = round(last_close * (1 - band_move_pct / 100), 2)
    band_upper = round(last_close * (1 + band_move_pct / 100), 2)
    return momentum_pct, daily_vol_pct, band_move_pct, band_lower, band_upper


def build_scenario_metrics(snapshot: SignalSnapshot) -> ScenarioMetrics | None:
    if signal_missing_kline(snapshot):
        return None
    momentum_pct, daily_vol_pct, band_move_pct, band_lower, band_upper = _estimate_bar_stats(snapshot.vt_symbol)
    return ScenarioMetrics(
        snapshot=snapshot,
        momentum_pct=momentum_pct,
        daily_vol_pct=daily_vol_pct,
        band_move_pct=band_move_pct,
        band_lower=band_lower,
        band_upper=band_upper,
    )


def batch_build_scenario_metrics(
    vt_symbols: list[str],
    snapshots: dict[str, SignalSnapshot],
) -> list[ScenarioMetrics]:
    if not vt_symbols:
        return []

    eligible = [vt_symbol for vt_symbol in vt_symbols if snapshots.get(vt_symbol) is not None and not signal_missing_kline(snapshots[vt_symbol])]
    if not eligible:
        return []

    def worker(vt_symbol: str) -> ScenarioMetrics:
        snapshot = snapshots[vt_symbol]
        metrics = build_scenario_metrics(snapshot)
        if metrics is None:
            raise RuntimeError(f"情景指标计算失败：{vt_symbol}")
        return metrics

    workers = pattern_load_max_workers(item_count=len(eligible))
    pairs = run_parallel_map(eligible, worker, max_workers=workers)
    return list(pairs)


def bullish_score(metrics: ScenarioMetrics) -> float:
    snapshot = metrics.snapshot
    score = 0.0
    if snapshot.fast_ma is not None and snapshot.slow_ma is not None:
        if snapshot.fast_ma > snapshot.slow_ma:
            score += 35.0
        elif snapshot.fast_ma < snapshot.slow_ma:
            score -= 20.0
    if snapshot.signal == "buy":
        score += 28.0
    elif snapshot.signal == "hold":
        score += 10.0
    elif snapshot.signal == "sell":
        score -= 28.0
    if metrics.momentum_pct is not None:
        score += min(max(metrics.momentum_pct * 4.0, -24.0), 32.0)
    if snapshot.strength is not None:
        score += snapshot.strength * 0.22
    if snapshot.volume_ratio_5d is not None and snapshot.volume_ratio_5d >= 1.2:
        score += 8.0
    return score


def bearish_score(metrics: ScenarioMetrics) -> float:
    snapshot = metrics.snapshot
    score = 0.0
    if snapshot.fast_ma is not None and snapshot.slow_ma is not None:
        if snapshot.fast_ma < snapshot.slow_ma:
            score += 35.0
        elif snapshot.fast_ma > snapshot.slow_ma:
            score -= 20.0
    if snapshot.signal == "sell":
        score += 28.0
    elif snapshot.signal == "hold":
        score += 6.0
    elif snapshot.signal == "buy":
        score -= 28.0
    if metrics.momentum_pct is not None:
        score += min(max(-metrics.momentum_pct * 4.0, -24.0), 32.0)
    if snapshot.strength is not None:
        score += max(0.0, (70.0 - snapshot.strength) * 0.15)
    if snapshot.volume_ratio_5d is not None and snapshot.volume_ratio_5d >= 1.2:
        score += 6.0
    return score


def volatility_score(metrics: ScenarioMetrics) -> float:
    vol = metrics.daily_vol_pct or 0.0
    momentum_abs = abs(metrics.momentum_pct or 0.0)
    volume_ratio = metrics.snapshot.volume_ratio_5d or 1.0
    return vol * 1.4 + momentum_abs * 0.6 + max(0.0, volume_ratio - 1.0) * 3.0


def _has_near_unlock_snapshot(snapshot: SignalSnapshot) -> bool:
    return _has_near_unlock(snapshot.vt_symbol)


def matches_scenario(metrics: ScenarioMetrics, *, variant: str) -> bool:
    snapshot = metrics.snapshot
    if signal_missing_kline(snapshot):
        return False
    if _has_near_unlock_snapshot(snapshot):
        return False
    if variant == "scenario_bull":
        if snapshot.signal == "sell" and signal_is_fresh(snapshot):
            return False
        if metrics.momentum_pct is not None and metrics.momentum_pct < -1.0:
            return False
        return bullish_score(metrics) >= MIN_BULL_SCORE
    if variant == "scenario_bear":
        if snapshot.signal == "buy" and signal_is_fresh(snapshot):
            return False
        if metrics.momentum_pct is not None and metrics.momentum_pct > 1.0:
            return False
        return bearish_score(metrics) >= MIN_BEAR_SCORE
    if variant == "scenario_volatile":
        if metrics.daily_vol_pct is None or metrics.daily_vol_pct < MIN_DAILY_VOL_PCT:
            return False
        momentum_abs = abs(metrics.momentum_pct or 0.0)
        volume_ratio = metrics.snapshot.volume_ratio_5d or 0.0
        if momentum_abs < 0.8 and volume_ratio < 1.05:
            return False
        return volatility_score(metrics) >= MIN_VOLATILITY_SCORE
    return False


def filter_scenario_metrics(
    metrics_list: list[ScenarioMetrics],
    *,
    variant: str,
) -> list[ScenarioMetrics]:
    return [metrics for metrics in metrics_list if matches_scenario(metrics, variant=variant)]


def classify_scenario_hint(metrics: ScenarioMetrics) -> str | None:
    """返回 5 日统计情景标签（偏多/偏空/高波动），无明确情景则 None。"""
    candidates: list[tuple[str, float]] = []
    for variant, score_fn in (
        ("scenario_bull", bullish_score),
        ("scenario_bear", bearish_score),
        ("scenario_volatile", volatility_score),
    ):
        if not matches_scenario(metrics, variant=variant):
            continue
        label = SCENARIO_VARIANT_LABELS[variant]
        candidates.append((label, score_fn(metrics)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates[0][0]


def scenario_sort_key(metrics: ScenarioMetrics, *, variant: str) -> tuple:
    snapshot = metrics.snapshot
    if variant == "scenario_bull":
        return (bullish_score(metrics), metrics.momentum_pct or -999.0, snapshot.strength or -999.0, snapshot.vt_symbol)
    if variant == "scenario_bear":
        return (bearish_score(metrics), -(metrics.momentum_pct or 999.0), snapshot.strength or -999.0, snapshot.vt_symbol)
    return (
        volatility_score(metrics),
        metrics.daily_vol_pct or 0.0,
        abs(metrics.momentum_pct or 0.0),
        snapshot.vt_symbol,
    )


def scenario_metrics_to_row(
    metrics: ScenarioMetrics,
    *,
    variant: str,
    name_map: dict[str, str],
) -> RadarRow:
    snapshot = metrics.snapshot
    item = parse_stock_symbol(snapshot.vt_symbol)
    name = name_map.get(snapshot.vt_symbol) or (item.name if item else "") or snapshot.vt_symbol
    symbol = item.symbol if item else snapshot.vt_symbol.split(".")[0]
    last_price = last_price_for_snapshot(snapshot.vt_symbol, snapshot)
    quote = merge_row_quotes({"vt_symbol": snapshot.vt_symbol})
    change_raw = quote.get("change_pct")
    change_pct = float(change_raw) if isinstance(change_raw, (int, float)) else None
    metric_label = SCENARIO_VARIANT_LABELS.get(variant, "情景")
    if variant == "scenario_volatile":
        metric_value = f"σ {metrics.daily_vol_pct:.1f}%" if metrics.daily_vol_pct is not None else "—"
    elif metrics.momentum_pct is not None:
        metric_value = f"{metrics.momentum_pct:+.1f}%"
    else:
        metric_value = "—"
    if metrics.band_lower is not None and metrics.band_upper is not None:
        sub_label = "参考带"
        sub_value = f"{metrics.band_lower:.2f}–{metrics.band_upper:.2f}"
    else:
        sub_label = "信号"
        sub_value = snapshot.signal_label
    return RadarRow(
        vt_symbol=snapshot.vt_symbol,
        name=name,
        symbol=symbol,
        price=last_price,
        change_pct=change_pct,
        metric_label=metric_label,
        metric_value=metric_value,
        sub_label=sub_label,
        sub_value=sub_value,
    )


def build_scenario_rows(
    metrics_list: tuple[ScenarioMetrics, ...],
    *,
    variant: str,
    name_map: dict[str, str],
) -> tuple[RadarRow, ...]:
    return tuple(scenario_metrics_to_row(metrics, variant=variant, name_map=name_map) for metrics in metrics_list)
