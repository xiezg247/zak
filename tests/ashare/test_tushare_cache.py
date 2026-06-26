"""Tushare 因子缓存测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

import tests._bootstrap  # noqa: F401
from vnpy_ashare.integrations.tushare.cache import (
    DATASET_DAILY_BASIC,
    clear_tushare_cache,
    get_cached_rows,
    set_cached_rows,
)


class TushareCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_tushare_cache()

    def tearDown(self) -> None:
        clear_tushare_cache()

    def test_cache_roundtrip(self) -> None:
        rows = [{"vt_symbol": "600519.SSE", "pe_ttm": 20.5}]
        set_cached_rows(DATASET_DAILY_BASIC, "20260605", rows)
        cached = get_cached_rows(DATASET_DAILY_BASIC, "20260605")
        self.assertEqual(cached, rows)

    def test_cache_miss_on_expired(self) -> None:
        from vnpy_ashare.storage.connection import connect

        stale_at = (datetime.now() - timedelta(hours=25)).isoformat(timespec="seconds")
        payload = '[{"vt_symbol": "600519.SSE"}]'
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO tushare_factor_cache(dataset, trade_date, fetched_at, payload)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (dataset, trade_date) DO UPDATE SET
                    fetched_at = EXCLUDED.fetched_at,
                    payload = EXCLUDED.payload
                """,
                (DATASET_DAILY_BASIC, "20260604", stale_at, payload),
            )
        cached = get_cached_rows(DATASET_DAILY_BASIC, "20260604", max_age=timedelta(hours=24))
        self.assertIsNone(cached)


if __name__ == "__main__":
    unittest.main()
