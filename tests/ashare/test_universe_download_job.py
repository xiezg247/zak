"""全市场日 K 下载任务测试。"""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.data.bar_store import PeriodBarOverview
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.jobs.bars.download import (
    DEFAULT_UNIVERSE_DAILY_START,
    _download_one,
    _is_no_data_error,
    _load_no_data_skips,
    _record_no_data_skip,
    batch_download_universe_daily_bars,
    parse_universe_daily_start,
    select_universe_daily_targets,
)


class UniverseDailyStartTests(unittest.TestCase):
    def test_parse_default_start(self) -> None:
        start = parse_universe_daily_start()
        self.assertEqual(start, datetime(2020, 1, 1))

    def test_parse_custom_start(self) -> None:
        start = parse_universe_daily_start("2021-06-01")
        self.assertEqual(start, datetime(2021, 6, 1))


class UniverseDownloadJobTests(unittest.TestCase):
    def test_skips_when_universe_missing(self) -> None:
        with patch("vnpy_ashare.jobs.bars.download.universe_exists", return_value=False):
            result = batch_download_universe_daily_bars()
        self.assertFalse(result.success)
        self.assertIn("同步 A 股列表", result.message)

    def test_skips_when_token_missing(self) -> None:
        from vnpy_ashare.integrations.tushare import TushareNotConfiguredError

        with patch("vnpy_ashare.jobs.bars.download.universe_exists", return_value=True):
            with patch(
                "vnpy_ashare.jobs.bars.download.get_tushare_pro",
                side_effect=TushareNotConfiguredError("no token"),
            ):
                result = batch_download_universe_daily_bars()
        self.assertTrue(result.skipped)

    def test_reports_all_present(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="茅台")
        with patch("vnpy_ashare.jobs.bars.download.universe_exists", return_value=True):
            with patch("vnpy_ashare.jobs.bars.download.get_tushare_pro", return_value=object()):
                with patch(
                    "vnpy_ashare.jobs.bars.download.load_universe_stock_items",
                    return_value=[item],
                ):
                    with patch(
                        "vnpy_ashare.jobs.bars.download.select_universe_daily_targets",
                        return_value=[],
                    ):
                        result = batch_download_universe_daily_bars()
        self.assertTrue(result.success)
        self.assertIn(DEFAULT_UNIVERSE_DAILY_START, result.message)

    def test_select_targets_includes_missing(self) -> None:
        item_a = StockItem(symbol="600519", exchange=Exchange.SSE, name="茅台")
        item_b = StockItem(symbol="000001", exchange=Exchange.SZSE, name="平安")
        overview = PeriodBarOverview(
            symbol="600519",
            exchange=Exchange.SSE,
            period="daily",
            start=datetime(2020, 1, 1),
            end=datetime(2025, 6, 1),
            count=100,
        )
        with patch(
            "vnpy_ashare.jobs.bars.download.iter_bar_overviews",
            return_value=[overview],
        ):
            targets = select_universe_daily_targets(
                [item_a, item_b],
                unified_start=datetime(2020, 1, 1),
            )
        self.assertEqual([item_b.vt_symbol], [item.vt_symbol for item in targets])

    def test_select_targets_includes_shallow_history(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="茅台")
        overview = PeriodBarOverview(
            symbol="600519",
            exchange=Exchange.SSE,
            period="daily",
            start=datetime(2024, 1, 2),
            end=datetime(2025, 6, 1),
            count=100,
        )
        with patch(
            "vnpy_ashare.jobs.bars.download.iter_bar_overviews",
            return_value=[overview],
        ):
            targets = select_universe_daily_targets(
                [item],
                unified_start=datetime(2020, 1, 1),
            )
        self.assertEqual([item.vt_symbol], [item.vt_symbol for item in targets])

    def test_select_targets_honors_no_data_skip_list(self) -> None:
        item_a = StockItem(symbol="000550", exchange=Exchange.SZSE, name="江铃")
        item_b = StockItem(symbol="000001", exchange=Exchange.SZSE, name="平安")
        with patch(
            "vnpy_ashare.jobs.bars.download.iter_bar_overviews",
            return_value=[],
        ):
            targets = select_universe_daily_targets(
                [item_a, item_b],
                unified_start=datetime(2020, 1, 1),
                skip_no_data={"000550.SZSE"},
            )
        self.assertEqual([item_b.vt_symbol], [item.vt_symbol for item in targets])

    def test_no_data_error_is_detected(self) -> None:
        self.assertTrue(_is_no_data_error(RuntimeError("未获取到数据: 000550.SZSE")))
        self.assertFalse(_is_no_data_error(RuntimeError("网络错误")))

    def test_download_one_skips_when_no_data(self) -> None:
        item = StockItem(symbol="000550", exchange=Exchange.SZSE, name="江铃")
        with patch(
            "vnpy_ashare.jobs.bars.download.download_bars",
            side_effect=RuntimeError("未获取到数据: 000550.SZSE"),
        ):
            with patch("vnpy_ashare.jobs.bars.download._record_no_data_skip") as record:
                outcome = _download_one(item, start=datetime(2025, 1, 1), end=datetime(2025, 6, 1))
        self.assertEqual(outcome.status, "skipped")
        record.assert_called_once()

    def test_batch_treats_no_data_as_success_with_skip_count(self) -> None:
        item = StockItem(symbol="000550", exchange=Exchange.SZSE, name="江铃")
        with patch("vnpy_ashare.jobs.bars.download.universe_exists", return_value=True):
            with patch("vnpy_ashare.jobs.bars.download.get_tushare_pro", return_value=object()):
                with patch(
                    "vnpy_ashare.jobs.bars.download.load_universe_stock_items",
                    return_value=[item],
                ):
                    with patch(
                        "vnpy_ashare.jobs.bars.download.select_universe_daily_targets",
                        return_value=[item],
                    ):
                        with patch(
                            "vnpy_ashare.jobs.bars.download._download_one",
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
        with patch("vnpy_ashare.jobs.bars.download.get_meta", return_value=None):
            with patch("vnpy_ashare.jobs.bars.download.set_meta") as set_meta:
                _record_no_data_skip("000550.SZSE", reason="未获取到数据: 000550.SZSE")
        self.assertTrue(set_meta.called)
        payload = set_meta.call_args[0][1]
        self.assertIn("000550.SZSE", payload)
        with patch("vnpy_ashare.jobs.bars.download.get_meta", return_value=payload):
            self.assertIn("000550.SZSE", _load_no_data_skips())


if __name__ == "__main__":
    unittest.main()
