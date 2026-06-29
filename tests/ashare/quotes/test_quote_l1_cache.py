"""进程内 L1 行情缓存测试。"""

from __future__ import annotations

import os
import unittest

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.quotes.core import quote_l1_cache as l1


def _sample_quote(symbol: str = "000001", *, change_pct: float = 1.0) -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol=symbol,
        name=f"测试{symbol}",
        last_price=10.0,
        prev_close=9.9,
        open_price=9.9,
        high_price=10.1,
        low_price=9.8,
        change_amount=0.1,
        change_pct=change_pct,
        turnover_rate=1.0,
        volume=1000.0,
    )


class QuoteL1CacheTests(unittest.TestCase):
    def setUp(self) -> None:
        l1.clear_quote_l1_cache()
        self._env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        l1.clear_quote_l1_cache()

    def test_disabled_by_default(self) -> None:
        os.environ.pop("ZAK_QUOTE_L1_CACHE", None)
        self.assertFalse(l1.quote_l1_enabled())
        self.assertIsNone(l1.try_get_quotes(["000001.SZ"]))

    def test_swap_and_read(self) -> None:
        os.environ["ZAK_QUOTE_L1_CACHE"] = "1"
        quotes = {
            "000001.SZ": _sample_quote("000001", change_pct=3.0),
            "600000.SH": _sample_quote("600000", change_pct=1.0),
        }
        l1.swap_quotes(quotes, updated_at="2026-06-26 10:00:00", complete=True)

        hit = l1.try_get_quotes(["600000.SH", "000001.SZ"])
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit["600000.SH"].change_pct, 1.0)

        rank = l1.try_list_rank_symbols()
        self.assertEqual(rank, ["000001.SZ", "600000.SH"])

    def test_partial_miss_falls_back(self) -> None:
        os.environ["ZAK_QUOTE_L1_CACHE"] = "1"
        l1.swap_quotes({"000001.SZ": _sample_quote()}, complete=True)
        self.assertIsNone(l1.try_get_quotes(["000001.SZ", "999999.SZ"]))

    def test_collect_defer_enrich_flag(self) -> None:
        os.environ.pop("ZAK_COLLECT_DEFER_ENRICH", None)
        self.assertFalse(l1.collect_defer_enrich_enabled())
        os.environ["ZAK_COLLECT_DEFER_ENRICH"] = "1"
        self.assertTrue(l1.collect_defer_enrich_enabled())

    def test_seq_matches_remote(self) -> None:
        os.environ["ZAK_QUOTE_L1_CACHE"] = "1"
        l1.swap_quotes({"000001.SZ": _sample_quote()}, seq=3, complete=True)
        self.assertTrue(l1.seq_matches(3))
        self.assertFalse(l1.seq_matches(4))
        self.assertFalse(l1.seq_matches(None))

    def test_merge_quotes_preserves_price(self) -> None:
        os.environ["ZAK_QUOTE_L1_CACHE"] = "1"
        base = _sample_quote()
        l1.swap_quotes({"000001.SZ": base}, complete=True)
        enriched = base.model_copy(update={"volume_ratio": 2.5, "net_mf_amount": 100.0})
        l1.merge_quotes({"000001.SZ": enriched})
        hit = l1.try_get_quotes(["000001.SZ"])
        assert hit is not None
        self.assertEqual(hit["000001.SZ"].last_price, base.last_price)
        self.assertEqual(hit["000001.SZ"].volume_ratio, 2.5)


if __name__ == "__main__":
    unittest.main()
