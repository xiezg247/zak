"""strategies.signals 单元测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

from strategies.signals import compute_double_ma_crosses, summarize_double_ma_state


def _make_series(length: int, *, start: float = 10.0, step: float = 0.0) -> tuple[list[float], list[datetime]]:
    closes: list[float] = []
    dates: list[datetime] = []
    price = start
    base = datetime(2024, 1, 2)
    for offset in range(length):
        closes.append(round(price, 2))
        dates.append(base + timedelta(days=offset))
        price += step
    return closes, dates


def test_golden_cross_detected():
    closes, dates = _make_series(40, start=10.0, step=-0.05)
    for index in range(25, 40):
        closes[index] = closes[index - 1] + 0.3

    signals = compute_double_ma_crosses(closes, dates, fast_window=5, slow_window=10)
    assert any(item.signal_type == "golden_cross" for item in signals)


def test_summarize_includes_current_ma():
    closes, dates = _make_series(35, start=10.0, step=0.1)
    summary = summarize_double_ma_state(closes, dates, fast_window=5, slow_window=10)
    assert summary["current"]["fast_ma"] is not None
    assert summary["current"]["slow_ma"] is not None
    assert "alignment" in summary["current"]


def test_insufficient_bars_returns_error():
    closes, dates = _make_series(5)
    summary = summarize_double_ma_state(closes, dates, fast_window=5, slow_window=10)
    assert "error" in summary
