"""market_breadth 单元测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.quotes.market_breadth import compute_market_breadth


class MarketBreadthTests(unittest.TestCase):
    def test_compute_counts_and_limits(self) -> None:
        rows = [
            {"change_pct": 10.0, "amount": 1e8},
            {"change_pct": 5.0, "amount": 2e8},
            {"change_pct": -10.0, "amount": 3e8},
            {"change_pct": 0.0, "amount": 0.0},
            {"change_pct": None, "amount": 1e8},
        ]
        snap = compute_market_breadth(rows, updated_at="12:00:00")
        self.assertEqual(snap.up, 2)
        self.assertEqual(snap.down, 1)
        self.assertEqual(snap.flat, 1)
        self.assertEqual(snap.limit_up, 1)
        self.assertEqual(snap.limit_down, 1)
        self.assertEqual(snap.sample_size, 4)
        self.assertAlmostEqual(snap.total_amount, 6e8)
        self.assertEqual(snap.updated_at, "12:00:00")

    def test_empty_rows(self) -> None:
        snap = compute_market_breadth([])
        self.assertEqual(snap.sample_size, 0)
        self.assertEqual(snap.total_amount, 0.0)


if __name__ == "__main__":
    unittest.main()
