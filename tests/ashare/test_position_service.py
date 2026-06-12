"""持仓 Service 测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from vnpy.trader.constant import Exchange

import tests._bootstrap  # noqa: F401
from vnpy_ashare.services.position_service import PositionService
from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.storage.repositories.positions import POSITION_MAX_ITEMS
from vnpy_ashare.storage.repositories.watchlist import add_watchlist_item


class PositionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.connection._db_path", return_value=self.db_path)
        self._patcher.start()
        init_app_db()
        add_watchlist_item("600000", Exchange.SSE, "浦发银行")
        engine = Mock()
        engine.main_engine = None
        engine.event_engine = None
        self.service = PositionService(engine)

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_add_and_remove_position(self) -> None:
        self.assertTrue(
            self.service.add(
                "600000",
                Exchange.SSE,
                cost_price=10.5,
                volume=100,
                buy_date="2026-06-01",
            )
        )
        items = self.service.get_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].volume, 100)
        self.assertAlmostEqual(items[0].cost_price, 10.5)
        self.assertTrue(self.service.remove("600000", Exchange.SSE))
        self.assertEqual(self.service.get_items(), [])

    def test_requires_watchlist_membership(self) -> None:
        self.assertFalse(
            self.service.add(
                "600519",
                Exchange.SSE,
                cost_price=10.0,
                volume=100,
                buy_date="2026-06-01",
            )
        )
        self.assertEqual(self.service.add_failure_reason("600519", Exchange.SSE), "not_in_watchlist")

    def test_fractional_cost_price_preserved(self) -> None:
        self.assertTrue(
            self.service.add(
                "600000",
                Exchange.SSE,
                cost_price=10.55,
                volume=100,
                buy_date="2026-06-01",
            )
        )
        self.assertAlmostEqual(self.service.get_items()[0].cost_price, 10.55)

    def test_normalize_volume_on_add(self) -> None:
        self.assertTrue(
            self.service.add(
                "600000",
                Exchange.SSE,
                cost_price=10.0,
                volume=150,
                buy_date="2026-06-01",
            )
        )
        self.assertEqual(self.service.get_items()[0].volume, 100)

    def test_position_max_items(self) -> None:
        for index in range(POSITION_MAX_ITEMS):
            symbol = f"{600001 + index}"
            add_watchlist_item(symbol, Exchange.SSE, f"测试{index}")
            self.assertTrue(
                self.service.add(
                    symbol,
                    Exchange.SSE,
                    cost_price=10.0,
                    volume=100,
                    buy_date="2026-06-01",
                )
            )
        self.assertTrue(self.service.at_capacity())
        add_watchlist_item("999999", Exchange.SSE, "溢出")
        self.assertFalse(
            self.service.add(
                "999999",
                Exchange.SSE,
                cost_price=10.0,
                volume=100,
                buy_date="2026-06-01",
            )
        )


if __name__ == "__main__":
    unittest.main()
