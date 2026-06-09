"""BacktestService 与 session_context 同步测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401

from vnpy_ashare.ai.session_context import clear_session_context, get_backtest_summary
from vnpy_ashare.services.backtest_service import BacktestService


class BacktestServiceSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_session_context()
        self.service = BacktestService(MagicMock())

    def tearDown(self) -> None:
        clear_session_context()

    def test_persist_summary_syncs_session_context(self) -> None:
        summary = {
            "strategy": "双均线策略",
            "vt_symbol": "600519.SSE",
            "interval": "d",
            "start": "2024-01-01",
            "end": "2024-12-31",
            "statistics": {"total_return": 12.5},
        }
        with patch(
            "vnpy_ashare.services.backtest_service.save_backtest_summary_dict",
        ) as mock_save:
            self.service.persist_summary(summary, source="single")
        mock_save.assert_called_once()
        cached = get_backtest_summary()
        assert cached is not None
        self.assertEqual(cached["strategy"], "双均线策略")
        self.assertEqual(cached["statistics"]["total_return"], 12.5)


if __name__ == "__main__":
    unittest.main()
