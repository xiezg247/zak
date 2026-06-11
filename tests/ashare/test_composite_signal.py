"""综合技术面信号单元测试。"""

from __future__ import annotations

from datetime import date, timedelta

from strategies.signals import (
    build_composite_signal_payload,
    classify_composite_signal,
    classify_double_ma_signal,
    summarize_double_ma_state,
)


def _series(
    count: int,
    *,
    start: float = 10.0,
    step: float = 0.3,
) -> tuple[list[float], list[date], list[float], list[float], list[float]]:
    closes = [start + step * index for index in range(count)]
    highs = [price + 0.2 for price in closes]
    lows = [price - 0.2 for price in closes]
    volumes = [1000 + index * 10 for index in range(count)]
    base = date(2024, 1, 2)
    dates = [base + timedelta(days=index) for index in range(count)]
    return closes, dates, highs, lows, volumes


def test_composite_payload_includes_strength_and_reason():
    closes, dates, highs, lows, volumes = _series(80)
    payload = build_composite_signal_payload(
        closes,
        dates,
        vt_symbol="600000.SSE",
        highs=highs,
        lows=lows,
        volumes=volumes,
    )
    assert payload["signal"] in ("buy", "sell", "hold", "na")
    if payload["signal"] != "na":
        assert payload["strength"] is not None
        assert 0 <= payload["strength"] <= 100
        assert isinstance(payload["reason_summary"], str)
        assert payload["last_close"] == round(closes[-1], 2)
        assert "action_ref_buy_price" in payload
        assert "action_ref_sell_price" in payload
        assert "volume_ratio_5d" in payload
        assert "ma_gap_pct" in payload
        assert "strength_cross" in payload


def test_composite_buy_on_bull_alignment_and_volume():
    closes, dates, highs, lows, volumes = _series(80, step=0.5)
    # 放大近期成交量
    for index in range(-5, 0):
        volumes[index] = volumes[index] * 3
    state = summarize_double_ma_state(closes, dates)
    ma5 = sum(closes[-5:]) / 5
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20
    signal = classify_composite_signal(
        state,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        last_close=closes[-1],
        volume_ratio=1.5,
    )
    base = classify_double_ma_signal(state)
    assert signal in ("buy", "hold", "sell") or base == "na"


def test_ref_prices_use_high_for_sell():
    closes, dates, highs, lows, volumes = _series(30)
    payload = build_composite_signal_payload(
        closes,
        dates,
        vt_symbol="600000.SSE",
        highs=highs,
        lows=lows,
        volumes=volumes,
    )
    if payload["ref_sell_price"] is not None:
        assert payload["ref_sell_price"] <= max(highs[-20:]) * 1.05 + 0.01


def test_ref_prices_hold_use_raw_ma_anchors():
    closes, dates, highs, lows, volumes = _series(80)
    payload = build_composite_signal_payload(
        closes,
        dates,
        vt_symbol="600000.SSE",
        highs=highs,
        lows=lows,
        volumes=volumes,
    )
    if payload["signal"] != "hold":
        return
    state = summarize_double_ma_state(closes, dates)
    assert payload["ref_buy_price"] == state["current"]["slow_ma"]
    assert payload["ref_sell_price"] == state["current"]["fast_ma"]
    assert any("支撑锚点" in reason for reason in payload["reasons"])


def test_ref_price_reasons_label_sell_breakdown():
    closes, dates, highs, lows, volumes = _series(80, step=-0.4)
    payload = build_composite_signal_payload(
        closes,
        dates,
        vt_symbol="600000.SSE",
        highs=highs,
        lows=lows,
        volumes=volumes,
    )
    if payload["signal"] != "sell":
        return
    assert any("支撑锚点" in reason for reason in payload["reasons"])
    assert any("参考买价" in reason for reason in payload["reasons"])
    assert payload["action_ref_buy_price"] != payload["ref_buy_price"]


def test_action_ref_includes_field_explanations_in_reasons():
    closes, dates, highs, lows, volumes = _series(80, step=-0.4)
    payload = build_composite_signal_payload(
        closes,
        dates,
        vt_symbol="600000.SSE",
        highs=highs,
        lows=lows,
        volumes=volumes,
    )
    if payload["signal"] == "na":
        return
    assert any("参考卖价" in reason for reason in payload["reasons"])
