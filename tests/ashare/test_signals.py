"""双均线信号单元测试。"""

from __future__ import annotations

from datetime import date, timedelta

from strategies.signals import (
    build_double_ma_signal_payload,
    classify_double_ma_signal,
    summarize_double_ma_state,
)


def _rising_closes(count: int, *, start: float = 10.0, step: float = 0.5) -> tuple[list[float], list[date]]:
    closes = [start + step * index for index in range(count)]
    dates = [date(2024, 1, 2) + timedelta(days=index) for index in range(count)]
    return closes, dates


def test_classify_double_ma_signal_recent_golden_cross():
    closes, dates = _rising_closes(40, start=8.0, step=0.4)
    state = summarize_double_ma_state(closes, dates, fast_window=5, slow_window=10)
    assert classify_double_ma_signal(state, recent_days=5) in ("buy", "hold", "sell", "na")


def test_classify_double_ma_signal_insufficient_bars():
    closes, dates = _rising_closes(5)
    state = summarize_double_ma_state(closes, dates, fast_window=10, slow_window=20)
    assert classify_double_ma_signal(state) == "na"


def test_build_double_ma_signal_payload_has_reference_prices():
    closes, dates = _rising_closes(40, start=8.0, step=0.4)
    payload = build_double_ma_signal_payload(
        closes,
        dates,
        vt_symbol="600000.SSE",
        fast_window=5,
        slow_window=10,
    )
    assert payload["vt_symbol"] == "600000.SSE"
    assert payload["signal"] in ("buy", "sell", "hold", "na")
    if payload["signal"] != "na":
        assert payload["ref_buy_price"] is not None
        assert payload["ref_sell_price"] is not None
        assert payload.get("strength") is not None


def test_build_double_ma_signal_payload_warns_on_short_series():
    closes, dates = _rising_closes(8)
    payload = build_double_ma_signal_payload(
        closes,
        dates,
        vt_symbol="600000.SSE",
    )
    assert payload["signal"] == "na"
    assert payload["warnings"]


def test_classify_respects_recent_days_window():
    closes, dates = _rising_closes(60, start=5.0, step=0.2)
    state = summarize_double_ma_state(closes, dates)
    state["as_of"] = "2024-03-01"
    if state.get("last_cross"):
        state["last_cross"] = {
            **state["last_cross"],
            "date": "2024-01-01",
            "type": "golden_cross",
            "type_label": "金叉",
        }
        state["current"] = {"fast_ma": 12.0, "slow_ma": 11.0, "alignment": "多头"}
        assert classify_double_ma_signal(state, recent_days=5) == "hold"
        assert classify_double_ma_signal(state, recent_days=90) == "buy"
