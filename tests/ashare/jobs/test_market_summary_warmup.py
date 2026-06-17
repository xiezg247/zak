"""市场摘要预热 job 测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.jobs.market_summary_warmup import warm_market_summary
from vnpy_ashare.quotes.market.emotion_cycle import peek_emotion_cycle_snapshot
from vnpy_ashare.quotes.market.market_summary_cache import peek_limit_ladder_counts
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError, MarketQuotesSnapshot


def test_warm_market_summary_skips_without_redis() -> None:
    with patch(
        "vnpy_ashare.jobs.market_summary_warmup.load_market_quote_rows",
        side_effect=MarketQuotesLoadError("无 Redis"),
    ):
        result = warm_market_summary(include_ladder=False)
    assert result.skipped
    assert peek_emotion_cycle_snapshot() is None


def test_warm_market_summary_stores_emotion_and_ladder() -> None:
    rows = [
        {
            "symbol": "000001",
            "vt_symbol": "000001.SZSE",
            "change_pct": 1.0,
            "amount": 1e8,
        }
    ]
    snapshot = MarketQuotesSnapshot(rows=rows, updated_at="2026-06-17T15:00:00", total=1)
    breadth = type("B", (), {"up": 1, "down": 0, "flat": 0, "limit_up": 1, "limit_down": 0, "total_amount": 1e12, "updated_at": "2026-06-17"})()

    with (
        patch("vnpy_ashare.jobs.market_summary_warmup.load_market_quote_rows", return_value=snapshot),
        patch("vnpy_ashare.jobs.market_summary_warmup._load_breadth", return_value=breadth),
        patch("vnpy_ashare.jobs.market_summary_warmup.compute_limit_ladder_counts", return_value={"首板": 1, "2板": 0, "3板": 0, "4板": 0, "5板+": 0}),
    ):
        result = warm_market_summary(include_ladder=True)

    assert result.success
    assert peek_emotion_cycle_snapshot() is not None
    assert peek_limit_ladder_counts() is not None
