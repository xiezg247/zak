"""行情快照序列化测试。"""

from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
