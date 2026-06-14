"""指数历史成交额测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.domain.index_amount import IndexAmountSeries
from vnpy_ashare.integrations.tushare.index_amount import (
    clear_index_amount_memory_cache,
    fetch_index_amount_history,
    index_daily_amount_to_yi,
)


class IndexAmountConversionTests(unittest.TestCase):
    def test_amount_thousand_yuan_to_yi(self) -> None:
        # 572383946 千元 ≈ 5723.84 亿
        self.assertAlmostEqual(index_daily_amount_to_yi(572383946), 5723.83946, places=2)


class IndexAmountHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_index_amount_memory_cache()

    def test_fetch_from_cached_rows(self) -> None:
        cached_rows = [{"ts_code": "000001.SH", "trade_date": f"2025060{i}", "amount": 100000 * i} for i in range(1, 8)]
        with patch(
            "vnpy_ashare.integrations.tushare.index_amount._latest_trade_date_str",
            return_value="20250607",
        ):
            with patch(
                "vnpy_ashare.integrations.tushare.index_amount.get_cached_rows",
                return_value=cached_rows,
            ):
                with patch(
                    "vnpy_ashare.integrations.tushare.index_amount.get_tushare_pro",
                ) as mock_pro:
                    series = fetch_index_amount_history("000001.SH", label="上证指数", trading_days=5)
        mock_pro.assert_not_called()
        self.assertIsInstance(series, IndexAmountSeries)
        self.assertEqual(series.label, "上证指数")
        self.assertEqual(len(series.points), 5)
        self.assertGreater(series.latest_yi, 0)

    def test_fetch_reports_error_when_empty(self) -> None:
        with patch(
            "vnpy_ashare.integrations.tushare.index_amount._latest_trade_date_str",
            return_value="20250607",
        ):
            with patch(
                "vnpy_ashare.integrations.tushare.index_amount.get_cached_rows",
                return_value=[],
            ):
                with patch(
                    "vnpy_ashare.integrations.tushare.index_amount._fetch_index_rows",
                    return_value=[],
                ):
                    series = fetch_index_amount_history("899050.BJ", label="北证50", trading_days=30)
        self.assertEqual(series.points, ())
        self.assertTrue(series.error)


if __name__ == "__main__":
    unittest.main()
