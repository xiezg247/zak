"""BacktestService 与 context_store 同步测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ai.context.store import clear_all, get_backtest_summary_dict
from vnpy_ashare.services.backtest import BacktestService


class BacktestServiceSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_all()
        self.service = BacktestService(MagicMock())

    def tearDown(self) -> None:
        clear_all()

    def test_persist_summary_syncs_context_store(self) -> None:
        summary = {
            "strategy": "双均线策略",
            "vt_symbol": "600519.SSE",
            "interval": "d",
            "start": "2024-01-01",
            "end": "2024-12-31",
            "statistics": {"total_return": 12.5},
        }
        with patch(
            "vnpy_ashare.services.backtest.save_backtest_summary_dict",
        ) as mock_save:
            self.service.persist_summary(summary, source="single")
        mock_save.assert_called_once()
        cached = get_backtest_summary_dict()
        assert cached is not None
        self.assertEqual(cached["strategy"], "双均线策略")
        self.assertEqual(cached["statistics"]["total_return"], 12.5)


if __name__ == "__main__":
    unittest.main()
