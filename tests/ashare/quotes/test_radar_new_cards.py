"""雷达新增卡片 loader 测试。"""

from unittest.mock import patch

from vnpy_ashare.quotes.radar.radar_catalog import RADAR_CARD_BY_ID, RADAR_CARD_SPECS, RadarCardSpec
from vnpy_ashare.quotes.radar.radar_loaders import collect_radar_risk_vt_symbols
from vnpy_ashare.quotes.radar.radar_market_emotion import is_stat_row, load_market_emotion
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow
from vnpy_ashare.quotes.radar.radar_position_risk import load_position_risk
from vnpy_ashare.quotes.radar.radar_resonance_prefs import (
    RADAR_CARDS_EXCLUDED_FROM_RESONANCE,
    radar_card_participates_in_resonance,
)
from vnpy_ashare.quotes.radar.radar_watchlist_short_term import load_watchlist_short_term


def test_new_cards_registered() -> None:
    ids = {spec.id for spec in RADAR_CARD_SPECS}
    for card_id in (
        "market_emotion",
        "discovery_limit_break",
        "watchlist_short_term",
        "sector_flow_hot",
    ):
        assert card_id in ids


def test_resonance_excludes_environment_and_risk_cards() -> None:
    assert "market_emotion" in RADAR_CARDS_EXCLUDED_FROM_RESONANCE
    assert "discovery_limit_break" in RADAR_CARDS_EXCLUDED_FROM_RESONANCE
    assert radar_card_participates_in_resonance("leader_pick")
    assert not radar_card_participates_in_resonance("market_emotion")


def test_collect_radar_risk_vt_symbols() -> None:
    payload = {
        "discovery_limit_break": RadarCardData(
            card_id="discovery_limit_break",
            title="发现·炸板断板",
            subtitle="",
            rows=(
                RadarRow(
                    vt_symbol="600000.SSE",
                    name="浦发银行",
                    symbol="600000",
                    price=10.0,
                    change_pct=-5.0,
                    metric_label="断板",
                    metric_value="3连",
                    sub_label="",
                    sub_value="",
                ),
            ),
            empty_message="",
            updated_at="t",
        )
    }
    assert collect_radar_risk_vt_symbols(payload) == frozenset({"600000.SSE"})


def test_load_watchlist_short_term_empty_group() -> None:
    spec = RADAR_CARD_BY_ID["watchlist_short_term"]
    with patch(
        "vnpy_ashare.quotes.radar.radar_watchlist_short_term.collect_short_term_focus_vt_symbols",
        return_value=[],
    ):
        data = load_watchlist_short_term(spec)
    assert data.rows == ()
    assert "短线关注" in data.empty_message


def test_is_stat_row() -> None:
    assert is_stat_row("__stat__:stage")
    assert not is_stat_row("600000.SSE")


def test_load_market_emotion_without_snapshot() -> None:
    spec = RadarCardSpec(id="market_emotion", title="盘面·环境", category="discovery")
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
