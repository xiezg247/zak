"""technical_snapshot 图表序列测试。"""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock

from vnpy_ashare.services.analysis_detail.technical.snapshot import TechnicalSnapshotMixin


class _FakeBar:
    def __init__(self, day: int, close: float) -> None:
        self.datetime = datetime(2026, 6, day)
        self.open_price = close - 0.5
        self.high_price = close + 0.5
        self.low_price = close - 1.0
        self.close_price = close
        self.volume = 1000 + day


class TechnicalSnapshotChartSeriesTests(unittest.TestCase):
    def test_snapshot_includes_chart_series(self) -> None:
        mixin = TechnicalSnapshotMixin()
        mixin._engine = MagicMock()
        bars = [_FakeBar(day, 10 + day * 0.1) for day in range(1, 25)]
        mixin._engine.bar_service.load_bars.return_value = bars
        mixin._engine.bar_service.get_return.return_value = {"return_pct": 3.2}

        result = mixin.technical_snapshot("600519.SSE", lookback=20)
        self.assertIn("chart_series", result)
        self.assertEqual(len(result["chart_series"]), 20)
        self.assertEqual(result["chart_series"][-1]["date"], "2026-06-24")


if __name__ == "__main__":
    unittest.main()
