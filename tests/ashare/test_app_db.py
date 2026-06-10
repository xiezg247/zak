"""元数据库测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage import app_db


class TestWatchlistDb(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.app_db.get_app_db_path", return_value=self.db_path)
        self._patcher.start()
        app_db.init_app_db()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_add_and_remove_watchlist(self) -> None:
        self.assertTrue(app_db.add_watchlist_item("600519", Exchange.SSE, "贵州茅台"))
        self.assertFalse(app_db.add_watchlist_item("600519", Exchange.SSE, "贵州茅台"))
        self.assertTrue(app_db.watchlist_contains("600519", Exchange.SSE))

        rows = app_db.load_watchlist_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "600519")

        self.assertTrue(app_db.remove_watchlist_item("600519", Exchange.SSE))
        self.assertFalse(app_db.remove_watchlist_item("600519", Exchange.SSE))
        self.assertEqual(app_db.load_watchlist_rows(), [])

    def test_move_watchlist_item(self) -> None:
        app_db.add_watchlist_item("600000", Exchange.SSE, "浦发银行")
        app_db.add_watchlist_item("600519", Exchange.SSE, "贵州茅台")
        app_db.add_watchlist_item("000001", Exchange.SZSE, "平安银行")

        self.assertFalse(app_db.move_watchlist_item("600000", Exchange.SSE, direction="up"))
        self.assertTrue(app_db.move_watchlist_item("600519", Exchange.SSE, direction="up"))
        self.assertEqual(
            [row[0] for row in app_db.load_watchlist_rows()],
            ["600519", "600000", "000001"],
        )
        self.assertTrue(app_db.move_watchlist_item("600000", Exchange.SSE, direction="down"))
        self.assertEqual(
            [row[0] for row in app_db.load_watchlist_rows()],
            ["600519", "000001", "600000"],
        )

    def test_load_universe_page(self) -> None:
        app_db.save_universe_rows(
            [
                ("600519", Exchange.SSE, "贵州茅台"),
                ("000001", Exchange.SZSE, "平安银行"),
                ("600000", Exchange.SSE, "浦发银行"),
            ]
        )
        rows, total = app_db.load_universe_page(offset=1, limit=1)
        self.assertEqual(total, 3)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "600000")


class TestSearchUniverse(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.app_db.get_app_db_path", return_value=self.db_path)
        self._patcher.start()
        app_db.init_app_db()
        app_db.save_universe_rows(
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
        rows, total = app_db.search_universe("600519")
        self.assertEqual(total, 1)
        self.assertEqual(rows[0][0], "600519")

        rows, total = app_db.search_universe("宁德")
        self.assertEqual(total, 1)
        self.assertEqual(rows[0][2], "宁德时代")

    def test_search_pagination(self) -> None:
        rows, total = app_db.search_universe("", limit=1, offset=0)
        self.assertEqual(total, 0)
        self.assertEqual(rows, [])

        rows, total = app_db.search_universe("平安", limit=1, offset=0)
        self.assertEqual(total, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], "平安银行")


if __name__ == "__main__":
    unittest.main()
