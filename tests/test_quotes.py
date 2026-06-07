"""行情模块测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare import app_db
from vnpy_ashare.quotes.snapshot import QuoteSnapshot


class TestQuoteSnapshot(unittest.TestCase):
    def test_redis_roundtrip(self) -> None:
        quote = QuoteSnapshot(
            symbol="600519.SH",
            name="贵州茅台",
            last_price=1700.0,
            prev_close=1680.0,
            open_price=1690.0,
            high_price=1710.0,
            low_price=1685.0,
            change_amount=20.0,
            change_pct=1.19,
            turnover_rate=0.35,
            volume=12345.0,
            amount=3_984_001_900.0,
            amplitude=1.20,
            trade_time="2026-06-05 15:00:02",
        )
        restored = QuoteSnapshot.from_redis_hash(quote.to_redis_hash())
        assert restored is not None
        self.assertEqual(restored.symbol, quote.symbol)
        self.assertEqual(restored.name, quote.name)
        self.assertAlmostEqual(restored.change_pct, quote.change_pct)
        self.assertAlmostEqual(restored.amount, quote.amount)
        self.assertAlmostEqual(restored.amplitude, quote.amplitude)
        self.assertEqual(restored.trade_time, quote.trade_time)


class TestSearchUniverse(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch.object(app_db, "APP_DB_PATH", self.db_path)
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
