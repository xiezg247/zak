"""Tushare Pro 交易日历缓存测试。"""

from __future__ import annotations

import unittest
from datetime import date, datetime
from unittest.mock import patch

from vnpy_ashare.storage.app_db import get_meta, set_meta
from vnpy_ashare.domain.calendar import is_trading_day, last_trading_day
from vnpy_ashare.storage.trade_calendar_store import (
    TRADE_CAL_SYNCED_AT_KEY,
    _upsert_rows,
    clear_trade_calendar_cache,
    ensure_calendar_covers,
    lookup_trading_day,
    sync_trade_calendar,
)


class TradeCalendarStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_trade_calendar_cache()

    def tearDown(self) -> None:
        clear_trade_calendar_cache()

    def test_lookup_uses_cached_holiday(self) -> None:
        _upsert_rows(
            [
                ("2026-01-28", 1),
                ("2026-01-29", 0),
                ("2026-01-30", 0),
            ]
        )
        set_meta(TRADE_CAL_SYNCED_AT_KEY, datetime.now().isoformat())

        self.assertTrue(lookup_trading_day(date(2026, 1, 28)))
        self.assertFalse(lookup_trading_day(date(2026, 1, 29)))
        self.assertIsNone(lookup_trading_day(date(2026, 2, 1)))

    def test_is_trading_day_prefers_cache_over_weekend_fallback(self) -> None:
        _upsert_rows([("2026-01-31", 1)])  # 2026-01-31 is Saturday
        set_meta(TRADE_CAL_SYNCED_AT_KEY, datetime.now().isoformat())

        self.assertTrue(is_trading_day(date(2026, 1, 31)))

    @patch("vnpy_ashare.storage.trade_calendar_store._fetch_trade_calendar")
    def test_sync_trade_calendar_writes_cache(self, fetch_mock) -> None:
        fetch_mock.return_value = [
            ("2026-06-01", 1),
            ("2026-06-02", 1),
            ("2026-06-03", 0),
        ]
        count = sync_trade_calendar(date(2026, 6, 1), date(2026, 6, 3))
        self.assertEqual(count, 3)
        self.assertTrue(lookup_trading_day(date(2026, 6, 1)))
        self.assertFalse(lookup_trading_day(date(2026, 6, 3)))
        self.assertIsNotNone(get_meta(TRADE_CAL_SYNCED_AT_KEY))

    @patch("vnpy_ashare.storage.trade_calendar_store.sync_trade_calendar")
    def test_ensure_calendar_covers_skips_when_fresh(self, sync_mock) -> None:
        _upsert_rows([("2026-06-05", 1)])
        set_meta(TRADE_CAL_SYNCED_AT_KEY, datetime.now().isoformat())
        set_meta("trade_calendar_range_start", "2026-01-01")
        set_meta("trade_calendar_range_end", "2026-12-31")

        self.assertTrue(ensure_calendar_covers(date(2026, 6, 5)))
        sync_mock.assert_not_called()

    @patch("vnpy_ashare.storage.trade_calendar_store._fetch_trade_calendar")
    def test_last_trading_day_uses_cached_holiday(self, fetch_mock) -> None:
        fetch_mock.return_value = [
            ("2026-02-13", 1),
            ("2026-02-14", 0),
            ("2026-02-15", 0),
            ("2026-02-16", 0),
            ("2026-02-17", 0),
            ("2026-02-18", 0),
            ("2026-02-19", 0),
            ("2026-02-20", 0),
            ("2026-02-23", 1),
        ]
        sync_trade_calendar(date(2026, 2, 13), date(2026, 2, 23))
        self.assertEqual(last_trading_day(on_or_before=date(2026, 2, 20)), date(2026, 2, 13))


if __name__ == "__main__":
    unittest.main()
