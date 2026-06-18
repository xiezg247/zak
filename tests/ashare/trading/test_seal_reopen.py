"""炸板回封检测测试。"""

from __future__ import annotations

import unittest
from datetime import datetime

from vnpy_ashare.trading.signals.seal_reopen import (
    classify_seal_reopen,
    detect_seal_reopen_from_minute_bars,
    format_seal_reopen_label,
    seal_reopen_score,
)


class _Bar:
    def __init__(self, dt: datetime, high: float, close: float) -> None:
        self.datetime = dt
        self.high_price = high
        self.close_price = close


class SealReopenTest(unittest.TestCase):
    def test_classify_from_open_times(self) -> None:
        self.assertEqual(classify_seal_reopen(open_times=0, at_limit=True), "solid")
        self.assertEqual(classify_seal_reopen(open_times=1, at_limit=True), "resealed")
        self.assertEqual(classify_seal_reopen(open_times=3, at_limit=True), "weak")
        self.assertEqual(classify_seal_reopen(open_times=1, at_limit=False), "unknown")

    def test_scores_and_labels(self) -> None:
        self.assertGreater(seal_reopen_score("solid"), seal_reopen_score("weak"))
        self.assertEqual(format_seal_reopen_label("resealed"), "炸板回封")
        self.assertIn("3", format_seal_reopen_label("weak", open_times=3))

    def test_minute_bars_solid(self) -> None:
        limit = 11.0
        bars = [
            _Bar(datetime(2026, 6, 18, 9, 35), 11.0, 11.0),
            _Bar(datetime(2026, 6, 18, 10, 0), 11.0, 11.0),
        ]
        kind, breaks = detect_seal_reopen_from_minute_bars(bars, limit_price=limit)
        self.assertEqual(kind, "solid")
        self.assertEqual(breaks, 0)

    def test_minute_bars_resealed(self) -> None:
        limit = 11.0
        bars = [
            _Bar(datetime(2026, 6, 18, 9, 35), 11.0, 11.0),
            _Bar(datetime(2026, 6, 18, 10, 0), 11.0, 10.5),
            _Bar(datetime(2026, 6, 18, 10, 15), 11.0, 11.0),
        ]
        kind, breaks = detect_seal_reopen_from_minute_bars(bars, limit_price=limit)
        self.assertEqual(kind, "resealed")
        self.assertEqual(breaks, 1)


if __name__ == "__main__":
    unittest.main()
