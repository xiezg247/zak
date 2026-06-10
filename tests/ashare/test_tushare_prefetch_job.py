"""Tushare 因子预拉取任务测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.jobs.tushare_prefetch import prefetch_tushare_factors
from vnpy_ashare.scheduler.manager import TaskSchedulerManager


class TusharePrefetchJobTests(unittest.TestCase):
    @patch("vnpy_ashare.jobs.tushare_prefetch.fetch_stock_industry_map", return_value={"600519.SH": "白酒"})
    @patch("vnpy_ashare.jobs.tushare_prefetch.fetch_daily_pct_map", return_value={"600519.SH": 1.2})
    @patch("vnpy_ashare.jobs.tushare_prefetch.fetch_moneyflow_with_fallback", return_value=([{"vt_symbol": "600519.SSE"}], "20260609"))
    @patch("vnpy_ashare.jobs.tushare_prefetch.fetch_daily_basic_with_fallback", return_value=([{"vt_symbol": "600519.SSE"}], "20260609"))
    @patch("vnpy_ashare.jobs.tushare_prefetch.get_tushare_pro")
    def test_prefetch_success(self, _pro_mock, *_mocks) -> None:
        result = prefetch_tushare_factors()
        self.assertTrue(result.success)
        self.assertIn("daily_basic", result.message)

    @patch("vnpy_ashare.jobs.tushare_prefetch.get_tushare_pro", side_effect=RuntimeError("未配置 TUSHARE_TOKEN"))
    def test_prefetch_skips_without_token(self, _pro_mock) -> None:
        from vnpy_ashare.screener.tushare_client import TushareNotConfiguredError

        with patch(
            "vnpy_ashare.jobs.tushare_prefetch.get_tushare_pro",
            side_effect=TushareNotConfiguredError("未配置 TUSHARE_TOKEN"),
        ):
            result = prefetch_tushare_factors()
        self.assertTrue(result.skipped)


class SchedulerPrefetchJobTests(unittest.TestCase):
    def test_prefetch_job_listed(self) -> None:
        manager = TaskSchedulerManager()
        job_ids = {item.job_id for item in manager.list_status()}
        self.assertIn("prefetch_tushare", job_ids)


if __name__ == "__main__":
    unittest.main()
