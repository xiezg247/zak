"""元数据库测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.storage.repositories import universe as universe_repo
from vnpy_ashare.storage.repositories import watchlist as watchlist_repo


class TestWatchlistDb(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.connection._db_path", return_value=self.db_path)
        self._patcher.start()
        init_app_db()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_add_and_remove_watchlist(self) -> None:
        self.assertTrue(watchlist_repo.add_watchlist_item("600519", Exchange.SSE, "贵州茅台"))
        self.assertFalse(watchlist_repo.add_watchlist_item("600519", Exchange.SSE, "贵州茅台"))
        self.assertTrue(watchlist_repo.watchlist_contains("600519", Exchange.SSE))

        rows = watchlist_repo.load_watchlist_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "600519")

        self.assertTrue(watchlist_repo.remove_watchlist_item("600519", Exchange.SSE))
        self.assertFalse(watchlist_repo.remove_watchlist_item("600519", Exchange.SSE))
        self.assertEqual(watchlist_repo.load_watchlist_rows(), [])

    def test_move_watchlist_item(self) -> None:
        watchlist_repo.add_watchlist_item("600000", Exchange.SSE, "浦发银行")
        watchlist_repo.add_watchlist_item("600519", Exchange.SSE, "贵州茅台")
        watchlist_repo.add_watchlist_item("000001", Exchange.SZSE, "平安银行")

        self.assertFalse(watchlist_repo.move_watchlist_item("600000", Exchange.SSE, direction="up"))
        self.assertTrue(watchlist_repo.move_watchlist_item("600519", Exchange.SSE, direction="up"))
        self.assertEqual(
            [row[0] for row in watchlist_repo.load_watchlist_rows()],
            ["600519", "600000", "000001"],
        )
        self.assertTrue(watchlist_repo.move_watchlist_item("600000", Exchange.SSE, direction="down"))
        self.assertEqual(
            [row[0] for row in watchlist_repo.load_watchlist_rows()],
            ["600519", "000001", "600000"],
        )

    def test_watchlist_max_items(self) -> None:
        for index in range(watchlist_repo.WATCHLIST_MAX_ITEMS):
            symbol = f"{600000 + index}"
            self.assertTrue(watchlist_repo.add_watchlist_item(symbol, Exchange.SSE, f"测试{index}"))
        self.assertEqual(watchlist_repo.watchlist_item_count(), watchlist_repo.WATCHLIST_MAX_ITEMS)
        self.assertTrue(watchlist_repo.watchlist_at_capacity())
        self.assertFalse(watchlist_repo.add_watchlist_item("999999", Exchange.SSE, "溢出"))
        self.assertEqual(watchlist_repo.watchlist_add_failure_reason("999999", Exchange.SSE), "full")
        self.assertEqual(watchlist_repo.watchlist_add_failure_reason("600000", Exchange.SSE), "duplicate")

    def test_load_universe_page(self) -> None:
        universe_repo.save_universe_rows(
            [
                ("600519", Exchange.SSE, "贵州茅台"),
                ("000001", Exchange.SZSE, "平安银行"),
                ("600000", Exchange.SSE, "浦发银行"),
            ]
        )
        rows, total = universe_repo.load_universe_page(offset=1, limit=1)
        self.assertEqual(total, 3)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "600000")


class TestSearchUniverse(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.connection._db_path", return_value=self.db_path)
        self._patcher.start()
        init_app_db()
        universe_repo.save_universe_rows(
            [
                ("600519", Exchange.SSE, "贵州茅台"),
                ("000001", Exchange.SZSE, "平安银行"),
                ("300750", Exchange.SZSE, "宁德时代"),
            ]
        )

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_search_by_symbol_and_name(self) -> None:
        rows, total = universe_repo.search_universe("600519")
        self.assertEqual(total, 1)
        self.assertEqual(rows[0][0], "600519")

        rows, total = universe_repo.search_universe("宁德")
        self.assertEqual(total, 1)
        self.assertEqual(rows[0][2], "宁德时代")

    def test_search_pagination(self) -> None:
        rows, total = universe_repo.search_universe("", limit=1, offset=0)
        self.assertEqual(total, 0)
        self.assertEqual(rows, [])

        rows, total = universe_repo.search_universe("平安", limit=1, offset=0)
        self.assertEqual(total, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], "平安银行")


if __name__ == "__main__":
    unittest.main()
