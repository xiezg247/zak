"""RedisQuoteStore 分批读取测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
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


    def test_get_quotes_uses_l1_when_enabled(self) -> None:
        import os

        from vnpy_ashare.quotes.core import quote_l1_cache as l1

        l1.clear_quote_l1_cache()
        prev = os.environ.get("ZAK_QUOTE_L1_CACHE")
        os.environ["ZAK_QUOTE_L1_CACHE"] = "1"
        try:
            quote = QuoteSnapshot(
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
            )
            l1.swap_quotes({"000001.SZ": quote}, complete=True)
            client = MagicMock()
            store = RedisQuoteStore(client=client)
            result = store.get_quotes(["000001.SZ"], enrich_factors=False)
            self.assertEqual(result["000001.SZ"].name, "平安")
            client.pipeline.assert_not_called()
        finally:
            l1.clear_quote_l1_cache()
            if prev is None:
                os.environ.pop("ZAK_QUOTE_L1_CACHE", None)
            else:
                os.environ["ZAK_QUOTE_L1_CACHE"] = prev


class RedisRankIncrementalTests(unittest.TestCase):
    def test_incremental_full_rank_skips_delete(self) -> None:
        from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
        from vnpy_ashare.quotes.core import redis_store as rs

        class _FakePipe:
            def __init__(self) -> None:
                self.ops: list[tuple] = []

            def hset(self, key: str, mapping: dict[str, str]) -> None:
                self.ops.append(("hset", key))

            def zadd(self, key: str, mapping: dict[str, float]) -> None:
                self.ops.append(("zadd", key, len(mapping)))

            def zrem(self, key: str, member: str) -> None:
                self.ops.append(("zrem", key, member))

            def delete(self, key: str) -> None:
                self.ops.append(("delete", key))

            def rpush(self, key: str, *values: str) -> None:
                self.ops.append(("rpush", key, len(values)))

            def set(self, key: str, value: str) -> None:
                self.ops.append(("set", key))

            def execute(self) -> None:
                return None

        class _FakeClient:
            def pipeline(self, transaction: bool = False):
                del transaction
                return self.pipe

            def get(self, key: str) -> str | None:
                del key
                return None

        pipe = _FakePipe()
        client = _FakeClient()
        client.pipe = pipe
        store = RedisQuoteStore(client=client)

        quote = QuoteSnapshot(
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
            volume_ratio=0.0,
        )

        prev = __import__("os").environ.get("ZAK_RANK_INCREMENTAL")
        __import__("os").environ["ZAK_RANK_INCREMENTAL"] = "1"
        try:
            with patch.object(rs, "apply_change_speed_5m"), patch.object(rs, "quote_l1_enabled", return_value=False):
                store.write_quotes({"000001.SZ": quote})
        finally:
            if prev is None:
                __import__("os").environ.pop("ZAK_RANK_INCREMENTAL", None)
            else:
                __import__("os").environ["ZAK_RANK_INCREMENTAL"] = prev

        deletes = [op for op in pipe.ops if op[0] == "delete"]
        change_pct_deletes = [op for op in deletes if op[1] == rs.rank_key("change_pct")]
        self.assertEqual(change_pct_deletes, [])
        zadd_ops = [op for op in pipe.ops if op[0] == "zadd" and op[1] == rs.rank_key("change_pct")]
        self.assertEqual(len(zadd_ops), 1)
        zrem_volume = [op for op in pipe.ops if op[0] == "zrem" and op[1] == rs.rank_key("volume_ratio")]
        self.assertGreaterEqual(len(zrem_volume), 1)


if __name__ == "__main__":
    unittest.main()
