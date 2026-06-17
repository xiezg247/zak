"""选股硬过滤：排除停牌。"""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from vnpy_ashare.domain.time.calendar import last_trading_day
from vnpy_ashare.screener.hard_filter_prefs import (
    HardFilterPrefs,
    default_hard_filter_prefs,
    save_hard_filter_prefs,
)
from vnpy_ashare.screener.hard_filters import (
    apply_recipe_filters,
    clear_suspend_screening_cache,
    recipe_exclude_suspended_enabled,
)
from vnpy_ashare.storage.connection import connect
from vnpy_ashare.storage.repositories.symbol_suspend import clear_symbol_suspend_cache


def _insert_suspend(symbol: str, exchange: str, cal_date: date) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO symbol_suspend_days(symbol, exchange, cal_date, suspend_type)
            VALUES (?, ?, ?, ?)
            """,
            (symbol, exchange, cal_date.isoformat(), "S"),
        )


class HardFiltersSuspendTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_symbol_suspend_cache()
        clear_suspend_screening_cache()
        save_hard_filter_prefs(
            HardFilterPrefs(
                exclude_st=False,
                exclude_suspended=True,
                min_amount_wan=0.0,
                min_total_mv_yi=0.0,
                exclude_new_listing=False,
                min_listing_days=60,
                exclude_limit_board=False,
                allowed_industries="",
                allowed_market_boards="",
            )
        )

    def tearDown(self) -> None:
        clear_symbol_suspend_cache()
        clear_suspend_screening_cache()
        save_hard_filter_prefs(default_hard_filter_prefs())

    def test_excludes_suspended_symbol(self) -> None:
        day = last_trading_day()
        _insert_suspend("600000", "SSE", day)
        rows = [
            {
                "vt_symbol": "600000.SSE",
                "symbol": "600000",
                "exchange": "SSE",
                "name": "浦发银行",
                "amount": 100_000_000,
            },
            {
                "vt_symbol": "000001.SZSE",
                "symbol": "000001",
                "exchange": "SZSE",
                "name": "平安银行",
                "amount": 100_000_000,
            },
        ]
        with patch(
            "vnpy_ashare.storage.repositories.symbol_suspend.sync_suspend_for_date",
            side_effect=AssertionError("不应触发远程同步"),
        ):
            filtered = apply_recipe_filters(rows)
        self.assertEqual([row["vt_symbol"] for row in filtered], ["000001.SZSE"])

    def test_disabled_exclude_suspended_keeps_rows(self) -> None:
        day = last_trading_day()
        _insert_suspend("600000", "SSE", day)
        save_hard_filter_prefs(
            HardFilterPrefs(
                exclude_st=False,
                exclude_suspended=False,
                min_amount_wan=0.0,
                min_total_mv_yi=0.0,
                exclude_new_listing=False,
                min_listing_days=60,
                exclude_limit_board=False,
                allowed_industries="",
                allowed_market_boards="",
            )
        )
        rows = [
            {
                "vt_symbol": "600000.SSE",
                "symbol": "600000",
                "exchange": "SSE",
                "name": "浦发银行",
            },
        ]
        filtered = apply_recipe_filters(rows)
        self.assertEqual(len(filtered), 1)
        self.assertTrue(recipe_exclude_suspended_enabled() is False)


if __name__ == "__main__":
    unittest.main()
