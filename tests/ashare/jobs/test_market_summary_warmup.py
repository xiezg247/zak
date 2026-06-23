"""market_summary 预热测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.domain.market.breadth import MarketBreadthSnapshot
from vnpy_ashare.jobs.market.summary_warmup import warm_market_summary
from vnpy_ashare.quotes.market.emotion_cycle import peek_emotion_cycle_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError, MarketQuotesSnapshot


def test_warm_market_summary_skips_without_redis() -> None:
    with patch(
        "vnpy_ashare.jobs.market.summary_warmup.load_intraday_market_snapshot",
        side_effect=MarketQuotesLoadError("无 Redis"),
    ):
        result = warm_market_summary(enrich_factors=False)
    assert result.skipped
    assert peek_emotion_cycle_snapshot() is None


def test_warm_market_summary_stores_emotion() -> None:
    rows = [
        {
            "symbol": "000001",
            "vt_symbol": "000001.SZ",
            "change_pct": 10.0,
            "amount": 1e8,
        }
    ]
    snapshot = MarketQuotesSnapshot(rows=rows, total=len(rows), updated_at="15:00")
    breadth = MarketBreadthSnapshot(
        up=1,
        down=0,
        flat=0,
        limit_up=1,
        limit_down=0,
        total_amount=1e8,
        sample_size=1,
        updated_at="15:00",
    )
    with (
        patch("vnpy_ashare.jobs.market.summary_warmup.load_intraday_market_snapshot", return_value=snapshot),
        patch("vnpy_ashare.jobs.market.summary_warmup._load_breadth", return_value=breadth),
    ):
        result = warm_market_summary(enrich_factors=True)

    assert result.success
    assert peek_emotion_cycle_snapshot() is not None
