"""moneyflow streak 批量计算测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.screener.engine.dimensions.moneyflow_streak import build_positive_moneyflow_streak_map


class MoneyflowStreakMapTests(unittest.TestCase):
    def test_counts_consecutive_positive_days(self) -> None:
        cached_by_date = {
            "20250625": [
                {"vt_symbol": "000001.SZ", "net_mf_amount": 100},
                {"vt_symbol": "600000.SH", "net_mf_amount": -1},
            ],
            "20250624": [
                {"vt_symbol": "000001.SZ", "net_mf_amount": 50},
            ],
            "20250623": [
                {"vt_symbol": "000001.SZ", "net_mf_amount": 10},
            ],
        }

        def _fake_iter(*, max_lookback: int, start=None):
            del max_lookback, start
            return ["20250625", "20250624", "20250623"]

        def _fake_cached(dataset: str, trade_date: str):
            del dataset
            return cached_by_date.get(trade_date)

        with (
            patch(
                "vnpy_ashare.screener.engine.dimensions.moneyflow_streak.iter_trade_date_strs",
                side_effect=_fake_iter,
            ),
            patch(
                "vnpy_ashare.screener.engine.dimensions.moneyflow_streak.get_cached_rows",
                side_effect=_fake_cached,
            ),
        ):
            result = build_positive_moneyflow_streak_map({"000001.SZ", "600000.SH"})

        self.assertEqual(result.get("000001.SZ"), 3)
        self.assertNotIn("600000.SH", result)

    def test_stops_when_symbol_missing_on_day(self) -> None:
        cached_by_date = {
            "20250625": [{"vt_symbol": "000001.SZ", "net_mf_amount": 1}],
            "20250624": [],
        }

        with (
            patch(
                "vnpy_ashare.screener.engine.dimensions.moneyflow_streak.iter_trade_date_strs",
                return_value=["20250625", "20250624"],
            ),
            patch(
                "vnpy_ashare.screener.engine.dimensions.moneyflow_streak.get_cached_rows",
                side_effect=lambda _dataset, trade_date: cached_by_date.get(trade_date),
            ),
        ):
            result = build_positive_moneyflow_streak_map({"000001.SZ"})

        self.assertEqual(result.get("000001.SZ"), 1)


if __name__ == "__main__":
    unittest.main()
