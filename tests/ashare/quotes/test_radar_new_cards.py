"""雷达新增卡片 loader 测试。"""

from unittest.mock import patch

from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.quotes.radar.radar_catalog import RADAR_CARD_BY_ID
from vnpy_ashare.quotes.radar.radar_horizon_rules import filter_avoid_snapshots, matches_avoid
from vnpy_ashare.quotes.radar.radar_market_emotion import is_stat_row, load_market_emotion
from vnpy_ashare.quotes.radar.radar_position_risk import load_position_risk


def test_is_stat_row() -> None:
    assert is_stat_row("__stat__:stage")
    assert not is_stat_row("600000.SSE")


def test_load_market_emotion_without_snapshot() -> None:
    spec = RADAR_CARD_BY_ID["market_emotion"]
    with patch(
        "vnpy_ashare.quotes.radar.radar_market_emotion.load_emotion_cycle_snapshot",
        return_value=None,
    ):
        data = load_market_emotion(spec)
    assert data.rows == ()
    assert "情绪" in data.empty_message or "广度" in data.empty_message


def test_load_position_risk_empty() -> None:
    spec = RADAR_CARD_BY_ID["position_risk"]
    with patch(
        "vnpy_ashare.quotes.radar.radar_position_risk.load_position_rows",
        return_value=[],
    ):
        data = load_position_risk(spec)
    assert data.rows == ()
    assert "持仓" in data.empty_message


def test_matches_avoid_sell_signal() -> None:
    snapshot = SignalSnapshot(
        vt_symbol="600000.SSE",
        strategy_id="AshareDoubleMaStrategy",
        as_of="2026-06-18",
        signal="sell",
        signal_label="卖出",
        strength=80.0,
        ref_buy_price=None,
        ref_sell_price=10.0,
        last_close=9.5,
        fast_ma=9.0,
        slow_ma=10.0,
        reasons=("死叉",),
        reason_summary="死叉",
        warnings=(),
        signal_date="2026-06-18",
    )
    assert matches_avoid(snapshot, last_price=9.5)


def test_filter_avoid_snapshots() -> None:
    sell = SignalSnapshot(
        vt_symbol="600000.SSE",
        strategy_id="AshareDoubleMaStrategy",
        as_of="2026-06-18",
        signal="sell",
        signal_label="卖出",
        strength=80.0,
        ref_buy_price=None,
        ref_sell_price=10.0,
        last_close=9.5,
        fast_ma=9.0,
        slow_ma=10.0,
        reasons=(),
        reason_summary="卖出",
        warnings=(),
        signal_date="2026-06-18",
    )
    hold = SignalSnapshot(
        vt_symbol="000001.SZSE",
        strategy_id="AshareDoubleMaStrategy",
        as_of="2026-06-18",
        signal="hold",
        signal_label="观望",
        strength=50.0,
        ref_buy_price=10.0,
        ref_sell_price=None,
        last_close=10.1,
        fast_ma=10.2,
        slow_ma=10.0,
        reasons=(),
        reason_summary="观望",
        warnings=(),
        signal_date="2026-06-18",
    )
    with patch(
        "vnpy_ashare.quotes.radar.radar_horizon_rules.signal_is_fresh",
        return_value=True,
    ):
        matched = filter_avoid_snapshots([sell, hold])
    assert len(matched) == 1
    assert matched[0].vt_symbol == "600000.SSE"
