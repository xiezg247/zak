"""RedisQuoteStore 分批读取测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore, _iter_symbol_batches


class IterSymbolBatchesTests(unittest.TestCase):
    def test_splits_evenly(self) -> None:
        batches = _iter_symbol_batches(["a", "b", "c", "d", "e"], 2)
        self.assertEqual(batches, [["a", "b"], ["c", "d"], ["e"]])


class RedisQuoteStoreBatchReadTests(unittest.TestCase):
    def test_get_quotes_uses_multiple_pipelines(self) -> None:
        client = MagicMock()
        pipe = MagicMock()
        client.pipeline.return_value = pipe
        store = RedisQuoteStore(client=client)
        store.get_updated_at = MagicMock(return_value=None)  # type: ignore[method-assign]

        batch_size = 400
        total = batch_size * 2 + 50
        symbols = [f"{index:06d}.SZ" for index in range(total)]
        pipe.execute.side_effect = [[{}] * len(batch) for batch in _iter_symbol_batches(symbols, batch_size)]

        with patch("vnpy_ashare.quotes.core.redis_store.QUOTE_READ_BATCH_SIZE", batch_size):
            result = store.get_quotes(symbols, enrich_factors=False)

        self.assertEqual(len(result), 0)
        self.assertEqual(client.pipeline.call_count, 3)
        self.assertEqual(pipe.execute.call_count, 3)
        self.assertEqual(pipe.hgetall.call_count, total)

    def test_get_rank_scores_uses_multiple_pipelines(self) -> None:
        client = MagicMock()
        pipe = MagicMock()
        client.pipeline.return_value = pipe
        store = RedisQuoteStore(client=client)

        batch_size = 300
        total = batch_size + 1
        symbols = [f"{index:06d}.SZ" for index in range(total)]
        pipe.execute.side_effect = [[1.0] * len(batch) for batch in _iter_symbol_batches(symbols, batch_size)]

        with patch("vnpy_ashare.quotes.core.redis_store.QUOTE_READ_BATCH_SIZE", batch_size):
            scores = store.get_rank_scores("change_pct", symbols)

        self.assertEqual(len(scores), total)
        self.assertEqual(client.pipeline.call_count, 2)
        self.assertEqual(pipe.execute.call_count, 2)

    def test_single_batch_when_under_limit(self) -> None:
        client = MagicMock()
        pipe = MagicMock()
        client.pipeline.return_value = pipe
        store = RedisQuoteStore(client=client)

        symbols = ["000001.SZ", "600000.SH"]
        pipe.execute.return_value = [None, None]

        scores_map = store.get_rank_scores("volume_ratio", symbols)
        self.assertEqual(scores_map, {})
        self.assertEqual(client.pipeline.call_count, 1)


if __name__ == "__main__":
    unittest.main()
