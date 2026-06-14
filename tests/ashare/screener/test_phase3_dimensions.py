"""Phase 3 维度与恐贪调制测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.screener.data.quote_freshness import ensure_fresh_quotes_for_screening
from vnpy_ashare.screener.dimensions.intraday_breakout import run_intraday_breakout
from vnpy_ashare.screener.dimensions.moneyflow_intraday import run_moneyflow_intraday
from vnpy_ashare.screener.sentiment.sentiment_gate import apply_sentiment_modulation
from vnpy_ashare.services.sentiment_service import FearGreedSnapshot


def _breakout_row(**overrides):
    base = {
        "vt_symbol": "600000.SSE",
        "symbol": "600000",
        "name": "浦发银行",
        "prev_close": 10.0,
        "open_price": 10.1,
        "high_price": 10.8,
        "low_price": 10.0,
        "last_price": 10.75,
        "change_pct": 7.5,
        "turnover_rate": 2.0,
        "amount": 80_000_000,
    }
    base.update(overrides)
    return base


class TestPhase3Dimensions(unittest.TestCase):
    def test_intraday_breakout_detects_prev_close_break(self) -> None:
        snapshot = type("Snap", (), {"rows": [_breakout_row()], "total": 1})()

        with patch(
            "vnpy_ashare.screener.dimensions.intraday_breakout.load_screening_quote_snapshot",
            return_value=snapshot,
        ):
            hits, scanned = run_intraday_breakout(5, weight=0.2)

        self.assertEqual(scanned, 1)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].dimension_id, "intraday_breakout")
        self.assertIn("突破", hits[0].reason)

    def test_intraday_breakout_skips_weak_moves(self) -> None:
        weak = _breakout_row(high_price=10.02, last_price=10.01, change_pct=0.1)
        snapshot = type("Snap", (), {"rows": [weak], "total": 1})()

        with patch(
            "vnpy_ashare.screener.dimensions.intraday_breakout.load_screening_quote_snapshot",
            return_value=snapshot,
        ):
            hits, _ = run_intraday_breakout(5, weight=0.2)

        self.assertEqual(hits, [])

    def test_moneyflow_intraday_proxy_ranking(self) -> None:
        rows = [
            {
                "vt_symbol": "600000.SSE",
                "symbol": "600000",
                "name": "A",
                "change_pct": 3.0,
                "amount": 100_000_000,
            },
            {
                "vt_symbol": "000001.SZSE",
                "symbol": "000001",
                "name": "B",
                "change_pct": 1.0,
                "amount": 200_000_000,
            },
        ]
        snapshot = type("Snap", (), {"rows": rows, "total": 2})()

        with (
            patch(
                "vnpy_ashare.screener.dimensions.moneyflow_resolve.load_screening_quote_snapshot",
                return_value=snapshot,
            ),
            patch(
                "vnpy_ashare.screener.dimensions.moneyflow_resolve.fetch_intraday_moneyflow_map",
                return_value={},
            ),
            patch(
                "vnpy_ashare.screener.dimensions.moneyflow_resolve.is_ashare_trading_session",
                return_value=True,
            ),
        ):
            hits, scanned = run_moneyflow_intraday(2, weight=0.15)

        self.assertEqual(scanned, 2)
        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0].vt_symbol, "600000.SSE")
        self.assertIn("代理", hits[0].reason)

    def test_sentiment_modulation_penalizes_fear(self) -> None:
        rows = [
            {
                "vt_symbol": "600000.SSE",
                "composite_score": 80.0,
                "dimensions": {"momentum": 90.0, "sector_strength": 70.0},
                "hit_reasons": ["动量"],
            }
        ]
        snapshot = FearGreedSnapshot(
            index=20.0,
            label="极度恐惧",
            trade_date="2026-06-10",
            as_of="2026-06-10 10:00:00",
            components=[],
        )

        with patch(
            "vnpy_ashare.screener.sentiment.sentiment_gate.try_fetch_fear_greed_index",
            return_value=snapshot,
        ):
            adjusted, meta = apply_sentiment_modulation(rows, enabled=True)

        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta["fear_greed_index"], 20.0)
        self.assertLess(adjusted[0]["composite_score"], 80.0)
        self.assertIn("sentiment_note", adjusted[0])

    def test_ensure_fresh_quotes_skips_collect_when_recent(self) -> None:
        with patch(
            "vnpy_ashare.screener.data.quote_freshness.quote_snapshot_age_seconds",
            return_value=30.0,
        ):
            ok, message = ensure_fresh_quotes_for_screening(max_age_seconds=90, collect_if_stale=True)

        self.assertTrue(ok)
        self.assertIn("30", message)


if __name__ == "__main__":
    unittest.main()
