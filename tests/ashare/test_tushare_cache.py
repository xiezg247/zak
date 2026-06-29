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
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from vnpy_ashare.integrations.tushare.cache import _repo
        from vnpy_common.storage.tables import tushare_factor_cache as tfc

        stale_at = (datetime.now() - timedelta(hours=25)).isoformat(timespec="seconds")
        payload = '[{"vt_symbol": "600519.SSE"}]'

        def _write(conn) -> None:
            stmt = pg_insert(tfc).values(
                dataset=DATASET_DAILY_BASIC,
                trade_date="20260604",
                fetched_at=stale_at,
                payload=payload,
            )
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[tfc.c.dataset, tfc.c.trade_date],
                    set_={"fetched_at": stmt.excluded.fetched_at, "payload": stmt.excluded.payload},
                )
            )

        _repo.run(_write)
        cached = get_cached_rows(DATASET_DAILY_BASIC, "20260604", max_age=timedelta(hours=24))
        self.assertIsNone(cached)


if __name__ == "__main__":
    unittest.main()
