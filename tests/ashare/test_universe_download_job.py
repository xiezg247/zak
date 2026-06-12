"""全市场日 K 下载任务测试。"""

from __future__ import annotations

import unittest
from datetime import date, datetime
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.jobs.universe_download import (
    UNIVERSE_DAILY_LOOKBACK,
    _download_one,
    _is_no_data_error,
    _load_no_data_skips,
    _record_no_data_skip,
    batch_download_universe_daily_bars,
    select_universe_missing_daily,
    universe_daily_window_start,
)


class RollingTradingDayTests(unittest.TestCase):
    def test_universe_window_uses_250_trading_days(self) -> None:
        open_days = [date(2025, 5, day) for day in range(1, 21)]
        with patch(
            "vnpy_ashare.domain.calendar.trading_days_between",
            return_value=open_days,
        ):
            with patch(
                "vnpy_ashare.domain.calendar.last_trading_day",
                return_value=date(2025, 5, 20),
            ):
                start = universe_daily_window_start(trading_days=5)
        self.assertEqual(start.date(), date(2025, 5, 16))


class UniverseDownloadJobTests(unittest.TestCase):
    def test_skips_when_universe_missing(self) -> None:
        with patch("vnpy_ashare.jobs.universe_download.universe_exists", return_value=False):
            result = batch_download_universe_daily_bars()
        self.assertFalse(result.success)
        self.assertIn("同步 A 股列表", result.message)

    def test_skips_when_token_missing(self) -> None:
        from vnpy_ashare.integrations.tushare import TushareNotConfiguredError

        with patch("vnpy_ashare.jobs.universe_download.universe_exists", return_value=True):
            with patch(
                "vnpy_ashare.jobs.universe_download.get_tushare_pro",
                side_effect=TushareNotConfiguredError("no token"),
            ):
                result = batch_download_universe_daily_bars()
        self.assertTrue(result.skipped)

    def test_reports_all_present(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="茅台")
        with patch("vnpy_ashare.jobs.universe_download.universe_exists", return_value=True):
            with patch("vnpy_ashare.jobs.universe_download.get_tushare_pro", return_value=object()):
                with patch(
                    "vnpy_ashare.jobs.universe_download.load_universe_stock_items",
                    return_value=[item],
                ):
                    with patch(
                        "vnpy_ashare.jobs.universe_download.select_universe_missing_daily",
                        return_value=[],
                    ):
                        result = batch_download_universe_daily_bars()
        self.assertTrue(result.success)
        self.assertIn(str(UNIVERSE_DAILY_LOOKBACK), result.message)

    def test_select_missing_excludes_downloaded(self) -> None:
        item_a = StockItem(symbol="600519", exchange=Exchange.SSE, name="茅台")
        item_b = StockItem(symbol="000001", exchange=Exchange.SZSE, name="平安")
        overview = type(
            "Overview",
            (),
            {"symbol": "600519", "exchange": Exchange.SSE, "period": "daily", "start": None, "end": None, "count": 1},
        )()
        with patch(
            "vnpy_ashare.jobs.universe_download.iter_bar_overviews",
            return_value=[overview],
        ):
            missing = select_universe_missing_daily([item_a, item_b])
        self.assertEqual([item_b.vt_symbol], [item.vt_symbol for item in missing])

    def test_select_missing_honors_no_data_skip_list(self) -> None:
        item_a = StockItem(symbol="000550", exchange=Exchange.SZSE, name="江铃")
        item_b = StockItem(symbol="000001", exchange=Exchange.SZSE, name="平安")
        with patch(
            "vnpy_ashare.jobs.universe_download.iter_bar_overviews",
            return_value=[],
        ):
            missing = select_universe_missing_daily([item_a, item_b], skip_no_data={"000550.SZSE"})
        self.assertEqual([item_b.vt_symbol], [item.vt_symbol for item in missing])

    def test_no_data_error_is_detected(self) -> None:
        self.assertTrue(_is_no_data_error(RuntimeError("未获取到数据: 000550.SZSE")))
        self.assertFalse(_is_no_data_error(RuntimeError("网络错误")))

    def test_download_one_skips_when_no_data(self) -> None:
        item = StockItem(symbol="000550", exchange=Exchange.SZSE, name="江铃")
        with patch(
            "vnpy_ashare.jobs.universe_download.download_bars",
            side_effect=RuntimeError("未获取到数据: 000550.SZSE"),
        ):
            with patch("vnpy_ashare.jobs.universe_download._record_no_data_skip") as record:
                outcome = _download_one(item, start=datetime(2025, 1, 1), end=datetime(2025, 6, 1))
        self.assertEqual(outcome.status, "skipped")
        record.assert_called_once()

    def test_batch_treats_no_data_as_success_with_skip_count(self) -> None:
        item = StockItem(symbol="000550", exchange=Exchange.SZSE, name="江铃")
        with patch("vnpy_ashare.jobs.universe_download.universe_exists", return_value=True):
            with patch("vnpy_ashare.jobs.universe_download.get_tushare_pro", return_value=object()):
                with patch(
                    "vnpy_ashare.jobs.universe_download.load_universe_stock_items",
                    return_value=[item],
                ):
                    with patch(
                        "vnpy_ashare.jobs.universe_download.select_universe_missing_daily",
                        return_value=[item],
                    ):
                        with patch(
                            "vnpy_ashare.jobs.universe_download._download_one",
                            return_value=type(
                                "Outcome",
                                (),
                                {"vt_symbol": item.vt_symbol, "status": "skipped", "reason": "未获取到数据"},
                            )(),
                        ):
                            result = batch_download_universe_daily_bars(max_workers=1)
        self.assertTrue(result.success)
        self.assertIn("跳过 1 只", result.message)

    def test_record_and_load_no_data_skips(self) -> None:
        with patch("vnpy_ashare.jobs.universe_download.get_meta", return_value=None):
            with patch("vnpy_ashare.jobs.universe_download.set_meta") as set_meta:
                _record_no_data_skip("000550.SZSE", reason="未获取到数据: 000550.SZSE")
        self.assertTrue(set_meta.called)
        payload = set_meta.call_args[0][1]
        self.assertIn("000550.SZSE", payload)
        with patch("vnpy_ashare.jobs.universe_download.get_meta", return_value=payload):
            self.assertIn("000550.SZSE", _load_no_data_skips())


if __name__ == "__main__":
    unittest.main()
