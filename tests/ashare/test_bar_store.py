"""分 K 本地存储测试。"""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

from vnpy_ashare.bar_store import load_period_bars


class BarStoreTests(unittest.TestCase):
    @patch("vnpy_ashare.bar_store.get_database")
    def test_load_period_bars(self, get_database_mock) -> None:
        database = MagicMock()
        get_database_mock.return_value = database
        bars = [
            BarData(
                symbol="600519",
                exchange=Exchange.SSE,
                datetime=datetime(2026, 6, 1, 10, 0),
                interval=Interval.MINUTE,
                open_price=1,
                high_price=1,
                low_price=1,
                close_price=1,
                volume=1,
                gateway_name="DB",
            )
        ]
        database.load_bar_data.return_value = bars

        loaded = load_period_bars(
            "600519",
            Exchange.SSE,
            "1m",
            datetime(2026, 6, 1, 9, 30),
            datetime(2026, 6, 1, 15, 0),
        )
        self.assertEqual(loaded, bars)
        database.load_bar_data.assert_called_once_with(
            "600519",
            Exchange.SSE,
            Interval.MINUTE,
            datetime(2026, 6, 1, 9, 30),
            datetime(2026, 6, 1, 15, 0),
        )


if __name__ == "__main__":
    unittest.main()
