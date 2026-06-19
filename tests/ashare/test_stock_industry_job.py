"""stock_industry 定时任务测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError
from vnpy_ashare.jobs.sync.stock_industry import sync_stock_industry_job


class StockIndustryJobTests(unittest.TestCase):
    def test_skips_when_token_missing(self) -> None:
        with patch(
            "vnpy_ashare.jobs.sync.stock_industry.get_tushare_pro",
            side_effect=TushareNotConfiguredError("no token"),
        ):
            result = sync_stock_industry_job()
        self.assertTrue(result.skipped)

    def test_reports_sw_industry_count(self) -> None:
        with patch("vnpy_ashare.jobs.sync.stock_industry.get_tushare_pro", return_value=object()):
            with patch(
                "vnpy_ashare.jobs.sync.stock_industry.sync_sw_industry_snapshot",
                return_value=({"600362.SH": "工业金属"}, 1),
            ) as sync_mock:
                result = sync_stock_industry_job()
        self.assertTrue(result.success)
        self.assertIn("申万2021 L2", result.message)
        sync_mock.assert_called_once_with(force=True)

    def test_falls_back_to_stock_basic(self) -> None:
        with patch("vnpy_ashare.jobs.sync.stock_industry.get_tushare_pro", return_value=object()):
            with patch(
                "vnpy_ashare.jobs.sync.stock_industry.sync_sw_industry_snapshot",
                return_value=({}, 0),
            ):
                with patch(
                    "vnpy_ashare.jobs.sync.stock_industry.fetch_stock_basic_snapshot",
                    return_value=([{"ts_code": "600519.SH", "industry": "白酒"}], 1),
                ) as fetch_mock:
                    result = sync_stock_industry_job()
        self.assertTrue(result.success)
        self.assertIn("stock_basic", result.message)
        fetch_mock.assert_called_once_with(force=True)

    def test_fails_when_both_empty(self) -> None:
        with patch("vnpy_ashare.jobs.sync.stock_industry.get_tushare_pro", return_value=object()):
            with patch(
                "vnpy_ashare.jobs.sync.stock_industry.sync_sw_industry_snapshot",
                return_value=({}, 0),
            ):
                with patch(
                    "vnpy_ashare.jobs.sync.stock_industry.fetch_stock_basic_snapshot",
                    return_value=([], 0),
                ):
                    result = sync_stock_industry_job()
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
