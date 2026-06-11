"""趋势均线 + ADX 信号单元测试。"""

from __future__ import annotations

from datetime import date, timedelta

from strategies.signals import (
    build_trend_ma_signal_payload,
    classify_trend_ma_signal,
    list_supported_signal_strategies,
    summarize_trend_ma_state,
    _compute_adx_at,
)


def _series(
    count: int,
    *,
    start: float = 10.0,
    step: float = 0.15,
) -> tuple[list[float], list[date], list[float], list[float], list[float]]:
    closes = [start + step * index for index in range(count)]
    highs = [price + 0.4 for price in closes]
    lows = [price - 0.4 for price in closes]
    volumes = [1000 + index * 15 for index in range(count)]
    base = date(2023, 1, 3)
    dates = [base + timedelta(days=index) for index in range(count)]
    return closes, dates, highs, lows, volumes


def test_trend_strategy_listed():
    assert "AshareTrendMaStrategy" in list_supported_signal_strategies()


def test_adx_computes_on_long_series():
    closes, dates, highs, lows, volumes = _series(120, step=0.2)
    adx = _compute_adx_at(highs, lows, closes, len(closes) - 1, period=14)
    assert adx is not None
    assert adx >= 0


def test_trend_payload_structure():
    closes, dates, highs, lows, volumes = _series(120, step=0.25)
    payload = build_trend_ma_signal_payload(
        closes,
        dates,
        vt_symbol="600000.SSE",
        highs=highs,
        lows=lows,
        volumes=volumes,
        relative_index_pct=1.5,
    )
    assert payload["strategy_id"] == "AshareTrendMaStrategy"
    assert payload["signal"] in ("buy", "sell", "hold", "na")
    if payload["signal"] != "na":
        assert payload["strength"] is not None


def test_classify_trend_respects_adx_and_recent_days():
    closes, dates, highs, lows, volumes = _series(120, step=0.12)
    state = summarize_trend_ma_state(
        closes,
        dates,
        highs,
        lows,
        fast_window=10,
        slow_window=30,
    )
    state["as_of"] = "2024-06-01"
    if state.get("last_cross"):
        state["last_cross"] = {
            **state["last_cross"],
            "date": "2024-01-01",
            "type": "golden_cross",
            "type_label": "金叉",
        }
        state["current"] = {
            **(state.get("current") or {}),
            "fast_ma": 20.0,
            "slow_ma": 18.0,
            "adx": 30.0,
            "above_slow_ma": True,
            "slow_slope": 0.05,
            "adx_pass": True,
        }
        assert classify_trend_ma_signal(state, recent_days=10) == "hold"
        assert classify_trend_ma_signal(state, recent_days=200) == "buy"


def test_trend_insufficient_bars_returns_na():
    closes, dates, highs, lows, volumes = _series(30)
    payload = build_trend_ma_signal_payload(
        closes,
        dates,
        vt_symbol="600000.SSE",
        highs=highs,
        lows=lows,
        volumes=volumes,
    )
    assert payload["signal"] == "na"
    assert payload["warnings"]
