"""P5 优化测试。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import patch

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

from vnpy_ashare.quotes.radar.radar_cross_refs import build_outlook_cross_ref_suffix
from vnpy_ashare.quotes.radar.radar_models import RadarRow
from vnpy_ashare.screener.dimensions.history_signals import (
    breaks_rolling_high,
    positive_day_count,
    rolling_high_before_last,
)
from vnpy_ashare.screener.dimensions.moneyflow_resolve import _moneyflow_score_adjustment
from vnpy_ashare.screener.dimensions.volume_ratio import _volume_ratio_tier_factor
from vnpy_ashare.screener.hard_filter_prefs import PRESET_AGGRESSIVE, PRESET_CONSERVATIVE, hard_filter_preset
from vnpy_ashare.screener.hard_filters import is_at_limit_board, is_new_listing
from vnpy_ashare.screener.sentiment.sentiment_gate import apply_sentiment_snapshot_prefilter


def _bars(closes: list[float]) -> list[BarData]:
    bars: list[BarData] = []
    for index, close in enumerate(closes):
        bars.append(
            BarData(
                symbol="600000",
                exchange=Exchange.SSE,
                datetime=datetime(2026, 1, index + 1),
                interval=Interval.DAILY,
                open_price=close,
                high_price=close + 0.2,
                low_price=close - 0.2,
                close_price=close,
                volume=1000,
                gateway_name="test",
            )
        )
    return bars


def test_rolling_high_breakout_signal() -> None:
    bars = _bars([10.0, 10.2, 10.1, 10.3, 10.4, 10.5])
    rolling = rolling_high_before_last(bars, lookback_days=3)
    assert rolling is not None
    assert breaks_rolling_high(10.7, rolling, 0.5)


def test_positive_day_count() -> None:
    bars = _bars([10.0, 10.1, 10.0, 10.2, 10.3, 10.4])
    assert positive_day_count(bars, window=5) >= 3


def test_volume_ratio_tier_factor() -> None:
    assert _volume_ratio_tier_factor(1.5) == 1.0
    assert _volume_ratio_tier_factor(2.5) == 1.06
    assert _volume_ratio_tier_factor(6.0) == 1.12


def test_moneyflow_streak_tiers() -> None:
    base = 80.0
    row3 = {"moneyflow_streak_days": 3, "net_mf_amount": 1000, "change_pct": 2.0}
    row5 = {"moneyflow_streak_days": 5, "net_mf_amount": 1000, "change_pct": 2.0}
    assert _moneyflow_score_adjustment(row5, base) > _moneyflow_score_adjustment(row3, base)


def test_is_new_listing_and_limit_board() -> None:
    recent = (date.today() - timedelta(days=20)).strftime("%Y%m%d")
    assert is_new_listing({"vt_symbol": "301086.SZSE", "list_date": recent})
    assert is_at_limit_board({"vt_symbol": "600000.SSE", "change_pct": 10.0, "symbol": "600000"})
    assert not is_at_limit_board({"vt_symbol": "600000.SSE", "change_pct": 5.0, "symbol": "600000"})


def test_aggressive_hard_filter_preset() -> None:
    prefs = hard_filter_preset(PRESET_AGGRESSIVE)
    assert prefs.min_amount_wan == 5000.0
    assert prefs.min_total_mv_yi == 30.0
    assert not prefs.exclude_limit_board


def test_conservative_hard_filter_preset() -> None:
    prefs = hard_filter_preset(PRESET_CONSERVATIVE)
    assert prefs.exclude_new_listing
    assert prefs.exclude_limit_board
    assert prefs.min_amount_wan == 5000.0


def test_sentiment_snapshot_prefilter_caps_high_momentum() -> None:
    rows = [{"change_pct": 12.0}, {"change_pct": 3.0}]
    with (
        patch("vnpy_ashare.screener.sentiment.sentiment_gate.sentiment_gate_enabled", return_value=True),
        patch(
            "vnpy_ashare.screener.sentiment.sentiment_gate.try_fetch_fear_greed_index",
            return_value=type("Snap", (), {"index": 20.0})(),
        ),
        patch("vnpy_ashare.screener.dimensions.momentum._momentum_change_bounds", return_value=(0.5, 9.5)),
    ):
        filtered = apply_sentiment_snapshot_prefilter(rows)
    assert len(filtered) == 1
    assert filtered[0]["change_pct"] == 3.0


def test_outlook_cross_ref_includes_resonance() -> None:
    rows = (RadarRow("600000.SSE", "浦发", "600000", 10.0, 1.0, "买入", "70", "事件", "—"),)
    with (
        patch("vnpy_ashare.quotes.radar.radar_cross_refs.latest_recipe_vt_symbols", return_value=set()),
        patch(
            "vnpy_ashare.quotes.radar.radar_cross_refs.latest_resonance_vt_symbols",
            return_value={"600000.SSE"},
        ),
    ):
        suffix = build_outlook_cross_ref_suffix(rows)
    assert "共振重合 1" in suffix
