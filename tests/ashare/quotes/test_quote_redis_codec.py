"""Redis 紧凑 field key 编解码测试。"""

from __future__ import annotations

import os
import unittest

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.quotes.core.quote_redis_codec import (
    encode_quote_hash,
    normalize_redis_hash,
    quote_compact_enabled,
)


def _sample_quote() -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol="000001",
        name="平安",
        last_price=10.5,
        prev_close=10.0,
        open_price=10.1,
        high_price=10.6,
        low_price=10.0,
        change_amount=0.5,
        change_pct=5.0,
        turnover_rate=1.2,
        volume=100000.0,
        amount=50_000_000.0,
        amplitude=6.0,
        volume_ratio=1.5,
        net_mf_amount=1200.0,
        change_speed_5m=0.8,
        limit_times=0.0,
        trade_time="2025-06-26 10:00:00",
    )


class QuoteRedisCodecTests(unittest.TestCase):
    def test_normalize_expands_short_keys(self) -> None:
        data = {"s": "000001", "n": "平安", "cp": "5.0", "lp": "10.5"}
        normalized = normalize_redis_hash(data)
        self.assertEqual(normalized["symbol"], "000001")
        self.assertEqual(normalized["change_pct"], "5.0")

    def test_from_redis_hash_accepts_compact_keys(self) -> None:
        compact = {"s": "000001", "n": "平安", "lp": "10.5", "pc": "10.0", "op": "10.1", "hi": "10.6", "lo": "10.0", "ca": "0.5", "cp": "5.0", "tr": "1.2", "v": "100000"}
        quote = QuoteSnapshot.from_redis_hash(compact)
        assert quote is not None
        self.assertEqual(quote.symbol, "000001")
        self.assertEqual(quote.change_pct, 5.0)

    def test_encode_compact_when_enabled(self) -> None:
        prev = os.environ.get("ZAK_REDIS_QUOTE_COMPACT")
        os.environ["ZAK_REDIS_QUOTE_COMPACT"] = "1"
        try:
            self.assertTrue(quote_compact_enabled())
            encoded = encode_quote_hash(_sample_quote())
            self.assertIn("s", encoded)
            self.assertNotIn("symbol", encoded)
            roundtrip = QuoteSnapshot.from_redis_hash(encoded)
            assert roundtrip is not None
            self.assertEqual(roundtrip.name, "平安")
            self.assertEqual(roundtrip.net_mf_amount, 1200.0)
        finally:
            if prev is None:
                os.environ.pop("ZAK_REDIS_QUOTE_COMPACT", None)
            else:
                os.environ["ZAK_REDIS_QUOTE_COMPACT"] = prev


if __name__ == "__main__":
    unittest.main()
