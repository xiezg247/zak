"""Redis 行情 JSON blob 编解码与 MGET 读路径测试。"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.quotes.core import quote_redis_codec as codec
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore


def _sample_quote() -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol="000001",
        name="平安",
        last_price=10.0,
        prev_close=9.9,
        open_price=9.9,
        high_price=10.1,
        low_price=9.8,
        change_amount=0.1,
        change_pct=1.0,
        turnover_rate=1.0,
        volume=1000.0,
        volume_ratio=2.5,
    )


class QuoteBlobCodecTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        quote = _sample_quote()
        blob = codec.encode_quote_blob(quote)
        decoded = codec.decode_quote_blob(blob)
        assert decoded is not None
        self.assertEqual(decoded.symbol, quote.symbol)
        self.assertEqual(decoded.change_pct, quote.change_pct)
        self.assertEqual(decoded.volume_ratio, quote.volume_ratio)


class RedisBlobReadTests(unittest.TestCase):
    def test_get_quotes_uses_mget_when_blob_enabled(self) -> None:
        quote = _sample_quote()
        blob = codec.encode_quote_blob(quote)
        client = MagicMock()
        client.mget.return_value = [blob]
        store = RedisQuoteStore(client=client)
        store.get_updated_at = MagicMock(return_value=None)  # type: ignore[method-assign]

        prev_compact = os.environ.get("ZAK_REDIS_QUOTE_COMPACT")
        prev_blob = os.environ.get("ZAK_REDIS_QUOTE_BLOB")
        os.environ["ZAK_REDIS_QUOTE_BLOB"] = "1"
        try:
            with patch("vnpy_ashare.quotes.core.redis_store.quote_l1_enabled", return_value=False):
                result = store.get_quotes(["000001.SZ"], enrich_factors=False)
        finally:
            if prev_blob is None:
                os.environ.pop("ZAK_REDIS_QUOTE_BLOB", None)
            else:
                os.environ["ZAK_REDIS_QUOTE_BLOB"] = prev_blob
            if prev_compact is None:
                os.environ.pop("ZAK_REDIS_QUOTE_COMPACT", None)
            else:
                os.environ["ZAK_REDIS_QUOTE_COMPACT"] = prev_compact

        self.assertEqual(result["000001.SZ"].name, "平安")
        client.mget.assert_called_once()
        client.pipeline.assert_not_called()


if __name__ == "__main__":
    unittest.main()
