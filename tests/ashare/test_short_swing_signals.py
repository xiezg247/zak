"""短线突破与波段回踩信号单元测试。"""

from __future__ import annotations

from datetime import date, timedelta

from strategies.signals import (
    build_short_breakout_signal_payload,
    build_swing_ma_signal_payload,
    classify_short_breakout_signal,
    classify_swing_ma_signal,
    compute_breakout_events,
    compute_swing_pullback_entries,
    list_supported_signal_strategies,
    summarize_short_breakout_state,
    summarize_swing_ma_state,
)


def _series(
    count: int,
    *,
    start: float = 10.0,
    step: float = 0.4,
) -> tuple[list[float], list[date], list[float], list[float], list[float]]:
    closes = [start + step * index for index in range(count)]
    highs = [price + 0.3 for price in closes]
    lows = [price - 0.3 for price in closes]
    volumes = [1000 + index * 20 for index in range(count)]
    base = date(2024, 1, 2)
    dates = [base + timedelta(days=index) for index in range(count)]
    return closes, dates, highs, lows, volumes


def test_supported_strategies_include_short_and_swing():
    names = list_supported_signal_strategies()
    assert "AshareShortBreakoutStrategy" in names
    assert "AshareSwingMaStrategy" in names
    assert "AshareTrendMaStrategy" in names


def test_breakout_events_on_rising_series_with_volume_spike():
    closes, dates, highs, lows, volumes = _series(40, step=0.5)
    for index in range(-5, 0):
        volumes[index] *= 3
    events = compute_breakout_events(
        closes,
        highs,
        dates,
        volumes,
        fast_window=5,
        slow_window=10,
        breakout_lookback=5,
        volume_ratio_min=1.2,
    )
    assert isinstance(events, list)


def test_short_breakout_payload_structure():
    closes, dates, highs, lows, volumes = _series(50, step=0.5)
    for index in range(-5, 0):
        volumes[index] *= 3
    payload = build_short_breakout_signal_payload(
        closes,
        dates,
        vt_symbol="600000.SSE",
        highs=highs,
        lows=lows,
        volumes=volumes,
    )
    assert payload["strategy_id"] == "AshareShortBreakoutStrategy"
    assert payload["signal"] in ("buy", "sell", "hold", "na")


def test_classify_short_breakout_respects_recent_days():
    closes, dates, highs, lows, volumes = _series(50, step=0.3)
    state = summarize_short_breakout_state(closes, highs, dates, volumes)
    state["as_of"] = "2024-03-01"
    if state.get("last_breakout"):
        state["last_breakout"] = {
            **state["last_breakout"],
            "date": "2024-01-01",
        }
        state["current"] = {**(state.get("current") or {}), "fast_ma": 12.0, "slow_ma": 11.0}
        assert classify_short_breakout_signal(state, recent_days=2) == "hold"
        assert classify_short_breakout_signal(state, recent_days=90) == "buy"


def test_swing_pullback_entries_scan():
    closes, dates, highs, lows, volumes = _series(80, step=0.25)
    entries = compute_swing_pullback_entries(
        closes,
        lows,
        dates,
        volumes,
        fast_window=5,
        slow_window=10,
        pullback_pct=5.0,
        pullback_wait_days=8,
    )
    assert isinstance(entries, list)


def test_swing_ma_payload_structure():
    closes, dates, highs, lows, volumes = _series(80, step=0.3)
    payload = build_swing_ma_signal_payload(
        closes,
        dates,
        vt_symbol="600000.SSE",
        highs=highs,
        lows=lows,
        volumes=volumes,
    )
    assert payload["strategy_id"] == "AshareSwingMaStrategy"
    assert payload["signal"] in ("buy", "sell", "hold", "na")


def test_classify_swing_ma_respects_recent_days():
    closes, dates, highs, lows, volumes = _series(80, step=0.2)
    state = summarize_swing_ma_state(
        closes,
        dates,
        volumes,
        lows=lows,
    )
    state["as_of"] = "2024-03-01"
    if state.get("last_entry"):
        state["last_entry"] = {
            **state["last_entry"],
            "date": "2024-01-01",
        }
        state["current"] = {**(state.get("current") or {}), "fast_ma": 12.0, "slow_ma": 11.0}
        assert classify_swing_ma_signal(state, recent_days=5) == "hold"
        assert classify_swing_ma_signal(state, recent_days=90) == "buy"
