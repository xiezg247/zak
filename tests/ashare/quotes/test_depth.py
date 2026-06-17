"""五档盘口测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.domain.market.depth_snapshot import DepthSnapshot


class TestDepthSnapshot(unittest.TestCase):
    def test_level_order(self) -> None:
        depth = DepthSnapshot(
            symbol="600000.SH",
            bid_prices=[9.72, 9.71, 9.70, 9.69, 9.68],
            bid_volumes=[100, 200, 300, 400, 500],
            ask_prices=[9.73, 9.74, 9.75, 9.76, 9.77],
            ask_volumes=[10, 20, 30, 40, 50],
        )
        asks = depth.ask_levels()
        bids = depth.bid_levels()
        self.assertEqual(asks[0][0], 5)
        self.assertEqual(asks[-1][0], 1)
        self.assertEqual(bids[0][0], 1)
        self.assertEqual(bids[-1][0], 5)
        self.assertAlmostEqual(asks[-1][1], 9.73)

    def test_from_tickflow(self) -> None:
        depth = DepthSnapshot.from_tickflow(
            {
                "symbol": "600519.SH",
                "bid_prices": [1.0],
                "bid_volumes": [2],
                "ask_prices": [1.1],
                "ask_volumes": [3],
                "timestamp": 123,
            }
        )
        self.assertEqual(depth.symbol, "600519.SH")
        self.assertEqual(depth.timestamp, 123)


if __name__ == "__main__":
    unittest.main()
