"""雷达卡片注册表测试。"""

from vnpy_ashare.quotes.radar.radar_catalog import (
    CARD_VARIANTS,
    RADAR_CARD_SPECS,
    RADAR_GRID_COLUMNS,
    RADAR_LAYOUT_SECTIONS,
    SCREEN_TASK_VARIANTS,
    list_radar_cards,
    list_radar_cards_for_mode,
    radar_card_mode,
    variants_for_card,
)


def test_radar_cards_count_and_categories() -> None:
    cards = list_radar_cards()
    assert len(cards) == 13
    categories = {card.category for card in cards}
    assert categories == {"screen", "discovery", "watchlist", "sector", "outlook"}
    assert RADAR_GRID_COLUMNS == 3


def test_radar_layout_sections_and_modes() -> None:
    assert len(RADAR_LAYOUT_SECTIONS) == 2
    assert [section.mode for section in RADAR_LAYOUT_SECTIONS] == ["statistical", "predictive"]
    statistical = list_radar_cards_for_mode("statistical")
    predictive = list_radar_cards_for_mode("predictive")
    assert len(statistical) == 9
    assert len(predictive) == 4
    assert all(spec.mode == "statistical" for spec in statistical)
    assert all(spec.mode == "predictive" for spec in predictive)
    assert {spec.id for spec in predictive} == {
        "outlook_watch",
        "outlook_hold",
        "outlook_scenario",
        "outlook_predict",
    }
    assert radar_card_mode("discovery_volume_surge") == "statistical"
    assert radar_card_mode("outlook_watch") == "predictive"


def test_radar_card_ids_unique() -> None:
    ids = [spec.id for spec in RADAR_CARD_SPECS]
    assert len(ids) == len(set(ids))


def test_screen_task_variants_defined() -> None:
    keys = {variant.key for variant in SCREEN_TASK_VARIANTS}
    assert keys == {"scheduled_intraday", "scheduled_post_close", "strategy"}


def test_card_variants_registry() -> None:
    assert variants_for_card("sector_theme") == CARD_VARIANTS["sector_theme"]
    assert variants_for_card("outlook_scenario") == CARD_VARIANTS["outlook_scenario"]
    assert variants_for_card("outlook_predict") == CARD_VARIANTS["outlook_predict"]
    assert variants_for_card("outlook_watch") == ()
    assert variants_for_card("outlook_hold") == ()
    assert variants_for_card("watchlist_intraday") == ()


def test_scenario_scores() -> None:
    from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
    from vnpy_ashare.quotes.radar.radar_horizon_scenario import (
        ScenarioMetrics,
        bearish_score,
        bullish_score,
        matches_scenario,
        volatility_score,
    )

    bull_snap = SignalSnapshot(
        vt_symbol="600000.SSE",
        strategy_id="AshareDoubleMaStrategy",
        as_of="2025-01-01",
        signal="buy",
        signal_label="买入",
        signal_date="2025-01-01",
        ref_buy_price=10.0,
        ref_sell_price=None,
        strength=72.0,
        reason_summary="",
        reasons=(),
        warnings=(),
        last_close=10.5,
        fast_ma=10.4,
        slow_ma=10.0,
        volume_ratio_5d=1.3,
    )
    bull_metrics = ScenarioMetrics(
        snapshot=bull_snap,
        momentum_pct=3.5,
        daily_vol_pct=2.5,
        band_move_pct=5.0,
        band_lower=9.9,
        band_upper=11.0,
    )
    assert bullish_score(bull_metrics) >= 38.0
    assert matches_scenario(bull_metrics, variant="scenario_bull")

    bear_snap = SignalSnapshot(
        vt_symbol="000001.SZSE",
        strategy_id="AshareDoubleMaStrategy",
        as_of="2025-01-01",
        signal="sell",
        signal_label="卖出",
        signal_date="2025-01-01",
        ref_buy_price=None,
        ref_sell_price=11.0,
        strength=40.0,
        reason_summary="",
        reasons=(),
        warnings=(),
        last_close=9.8,
        fast_ma=9.5,
        slow_ma=10.0,
        volume_ratio_5d=1.2,
    )
    bear_metrics = ScenarioMetrics(
        snapshot=bear_snap,
        momentum_pct=-3.2,
        daily_vol_pct=2.8,
        band_move_pct=5.5,
        band_lower=9.4,
        band_upper=10.3,
    )
    assert bearish_score(bear_metrics) >= 38.0
    assert matches_scenario(bear_metrics, variant="scenario_bear")
    assert volatility_score(bull_metrics) > 0


def test_auto_refresh_intervals() -> None:
    from vnpy_ashare.quotes.radar.radar_catalog import (
        RADAR_CARD_BY_ID,
        RADAR_DISCOVERY_AUTO_REFRESH_MS,
        RADAR_SECTOR_AUTO_REFRESH_MS,
        RADAR_WATCHLIST_AUTO_REFRESH_MS,
        auto_refresh_card_ids,
        manual_only_card_ids,
    )

    auto_ids = auto_refresh_card_ids()
    assert "discovery_volume_surge" in auto_ids
    assert "watchlist_intraday" in auto_ids
    assert "discovery_first_board" in auto_ids
    manual_ids = manual_only_card_ids()
    assert "outlook_watch" in manual_ids
    assert "outlook_scenario" in manual_ids
    assert "screen_latest" in manual_ids
    assert RADAR_CARD_BY_ID["discovery_volume_surge"].auto_refresh_ms == RADAR_DISCOVERY_AUTO_REFRESH_MS
    assert RADAR_CARD_BY_ID["watchlist_intraday"].auto_refresh_ms == RADAR_WATCHLIST_AUTO_REFRESH_MS
    assert RADAR_CARD_BY_ID["sector_theme"].auto_refresh_ms == RADAR_SECTOR_AUTO_REFRESH_MS
    assert RADAR_CARD_BY_ID["outlook_hold"].auto_refresh_ms is None


def test_refresh_options_and_supports() -> None:
    from vnpy_ashare.quotes.radar.radar_catalog import (
        RADAR_DISCOVERY_REFRESH_OPTIONS,
        RADAR_REFRESH_OFF_MS,
        RADAR_SECTOR_REFRESH_OPTIONS,
        refresh_options_for_card,
        supports_auto_refresh,
    )

    assert supports_auto_refresh("discovery_volume_surge")
    assert supports_auto_refresh("sector_theme")
    assert not supports_auto_refresh("outlook_watch")
    assert not supports_auto_refresh("screen_latest")
    assert refresh_options_for_card("discovery_volume_surge") == RADAR_DISCOVERY_REFRESH_OPTIONS
    assert refresh_options_for_card("sector_theme") == RADAR_SECTOR_REFRESH_OPTIONS
    assert refresh_options_for_card("outlook_watch") == ()
    off_labels = {opt.label for opt in RADAR_DISCOVERY_REFRESH_OPTIONS if opt.ms == RADAR_REFRESH_OFF_MS}
    assert off_labels == {"不刷新"}
