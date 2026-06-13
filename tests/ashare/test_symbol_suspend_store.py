"""停牌日 repository 测试。"""

from __future__ import annotations

import unittest
from datetime import date, datetime
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.data.bar_health import BarMeta, find_gaps, inspect_bar_gaps
from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.storage.repositories.symbol_suspend import (
    clear_symbol_suspend_cache,
    load_suspend_days,
    sync_suspend_for_date,
)


class SymbolSuspendStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        init_app_db()
        clear_symbol_suspend_cache()

    def tearDown(self) -> None:
        clear_symbol_suspend_cache()

    @patch("vnpy_ashare.storage.repositories.symbol_suspend.fetch_suspend_d")
    def test_sync_and_load_suspend_days(self, fetch_mock) -> None:
        fetch_mock.return_value = [
            {
                "symbol": "000063",
                "exchange": "SZSE",
                "cal_date": "2026-06-03",
                "suspend_type": "S",
            }
        ]
        count = sync_suspend_for_date(date(2026, 6, 3))
        self.assertEqual(count, 1)
        days = load_suspend_days("000063", Exchange.SZSE, date(2026, 6, 1), date(2026, 6, 7))
        self.assertEqual(days, {date(2026, 6, 3)})

    @patch("vnpy_ashare.data.bar_health.load_suspend_days")
    def test_inspect_bar_gaps_ignores_suspend_days(self, load_mock) -> None:
        load_mock.return_value = {date(2026, 6, 2), date(2026, 6, 3), date(2026, 6, 4)}
        meta = BarMeta(
            start=datetime(2026, 6, 1),
            end=datetime(2026, 6, 5),
            count=2,
        )
        bar_dates = {date(2026, 6, 1), date(2026, 6, 5)}
        result = inspect_bar_gaps(
            meta,
            bar_dates,
            as_of=date(2026, 6, 5),
            symbol="000063",
            exchange=Exchange.SZSE,
        )
        self.assertEqual(result.status.value, "ok")
        self.assertEqual(result.gaps, [])

    def test_find_gaps_without_symbol_still_flags_missing(self) -> None:
        meta = BarMeta(
            start=datetime(2026, 6, 1),
            end=datetime(2026, 6, 5),
            count=2,
        )
        bar_dates = {date(2026, 6, 1), date(2026, 6, 5)}
        gaps = find_gaps(meta, bar_dates)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].start, date(2026, 6, 2))


if __name__ == "__main__":
    unittest.main()
