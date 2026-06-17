"""Tushare 预拉与本地补全任务测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError
from vnpy_ashare.jobs.bars.batch_fill import batch_fill_downloaded_stale_job
from vnpy_ashare.jobs.bars.local_fill import BatchFillResult
from vnpy_ashare.jobs.prefetch.moneyflow import prefetch_moneyflow
from vnpy_ashare.jobs.prefetch.tushare import prefetch_tushare_factors


class MoneyflowPrefetchJobTests(unittest.TestCase):
    def test_skips_when_token_missing(self) -> None:
        with patch(
            "vnpy_ashare.jobs.prefetch.moneyflow.get_tushare_pro",
            side_effect=TushareNotConfiguredError("no token"),
        ):
            result = prefetch_moneyflow()
        self.assertTrue(result.skipped)

    def test_prefetch_reports_moneyflow(self) -> None:
        with patch("vnpy_ashare.jobs.prefetch.moneyflow.get_tushare_pro", return_value=object()):
            with patch(
                "vnpy_ashare.jobs.prefetch.moneyflow.fetch_moneyflow",
                return_value=([{"vt_symbol": "600519.SSE"}], "20250609"),
            ):
                result = prefetch_moneyflow()
        self.assertTrue(result.success)
        self.assertIn("moneyflow", result.message)

    def test_fails_when_no_rows(self) -> None:
        with patch("vnpy_ashare.jobs.prefetch.moneyflow.get_tushare_pro", return_value=object()):
            with patch(
                "vnpy_ashare.jobs.prefetch.moneyflow.fetch_moneyflow",
                return_value=([], None),
            ):
                result = prefetch_moneyflow()
        self.assertFalse(result.success)


class TusharePrefetchJobTests(unittest.TestCase):
    def test_skips_when_token_missing(self) -> None:
        with patch(
            "vnpy_ashare.jobs.prefetch.tushare.get_tushare_pro",
            side_effect=TushareNotConfiguredError("no token"),
        ):
            result = prefetch_tushare_factors()
        self.assertTrue(result.skipped)

    def test_prefetch_reports_extended_datasets(self) -> None:
        with patch("vnpy_ashare.jobs.prefetch.tushare.get_tushare_pro", return_value=object()):
            with patch(
                "vnpy_ashare.jobs.prefetch.tushare.fetch_daily_basic_with_fallback",
                return_value=([{"vt_symbol": "600519.SSE"}], "20250609"),
            ):
                with patch(
                    "vnpy_ashare.jobs.prefetch.tushare.fetch_daily_pct_map",
                    return_value={"600519.SH": 1.2},
                ):
                    with patch(
                        "vnpy_ashare.jobs.prefetch.tushare.fetch_limit_list_d",
                        return_value=([{"ts_code": "600519.SH", "limit": "U"}], "20250609"),
                    ):
                        with patch(
                            "vnpy_ashare.jobs.prefetch.tushare.fetch_index_daily_snapshot",
                            return_value=([{"ts_code": "000300.SH"}], "20250609"),
                        ):
                            with patch(
                                "vnpy_ashare.jobs.prefetch.tushare.fetch_moneyflow_hsgt_window",
                                return_value=([{"north_money": 1.0}], "20250609"),
                            ):
                                with patch(
                                    "vnpy_ashare.jobs.prefetch.tushare.fetch_stock_basic_snapshot",
                                    return_value=([{"ts_code": "600519.SH"}], 1),
                                ):
                                    result = prefetch_tushare_factors()
        self.assertTrue(result.success)
        self.assertIn("limit_list_d", result.message)
        self.assertIn("index_daily", result.message)
        self.assertIn("moneyflow_hsgt", result.message)
        self.assertIn("stock_basic", result.message)


class BatchFillDownloadedJobTests(unittest.TestCase):
    def test_skips_when_no_downloaded_stocks(self) -> None:
        with patch(
            "vnpy_ashare.jobs.bars.batch_fill.load_downloaded_stocks",
            return_value=[],
        ):
            result = batch_fill_downloaded_stale_job()
        self.assertTrue(result.skipped)

    def test_reports_up_to_date(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="茅台")
        with patch(
            "vnpy_ashare.jobs.bars.batch_fill.load_downloaded_stocks",
            return_value=[item],
        ):
            with patch(
                "vnpy_ashare.jobs.bars.batch_fill.build_daily_bar_meta",
                return_value={},
            ):
                with patch(
                    "vnpy_ashare.jobs.bars.batch_fill.select_stale_daily_items",
                    return_value=[],
                ):
                    result = batch_fill_downloaded_stale_job()
        self.assertTrue(result.success)
        self.assertIn("均已是最新", result.message)

    def test_runs_batch_fill_for_stale_items(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="茅台")
        with patch(
            "vnpy_ashare.jobs.bars.batch_fill.load_downloaded_stocks",
            return_value=[item],
        ):
            with patch(
                "vnpy_ashare.jobs.bars.batch_fill.build_daily_bar_meta",
                return_value={},
            ):
                with patch(
                    "vnpy_ashare.jobs.bars.batch_fill.select_stale_daily_items",
                    return_value=[item],
                ):
                    with patch(
                        "vnpy_ashare.jobs.bars.batch_fill.batch_fill_stale_daily_bars",
                        return_value=BatchFillResult(
                            attempted=1,
                            success=1,
                            failed=[],
                            bars_added=3,
                            up_to_date=0,
                        ),
                    ):
                        result = batch_fill_downloaded_stale_job()
        self.assertTrue(result.success)
        self.assertIn("新增 3 根", result.message)


if __name__ == "__main__":
    unittest.main()
