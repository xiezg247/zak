"""雷达卡片布局纯函数。"""

from __future__ import annotations

from vnpy_ashare.ui.quotes.radar.card_layout import (
    card_frame_object_name,
    card_shows_add_watchlist_actions,
    card_shows_sector_actions,
    count_resonance_hits,
    estimate_card_min_height,
    fallback_visible_card_ids,
    format_card_meta,
    kind_badge_presentation,
    mode_badge_presentation,
)


def test_estimate_card_min_height_scales_with_top_n() -> None:
    h1 = estimate_card_min_height(1)
    h3 = estimate_card_min_height(3)
    assert h1 > 100
    assert h3 > h1
    assert estimate_card_min_height(0) == h1


def test_card_frame_object_name() -> None:
    assert card_frame_object_name(mode="predictive", supports_auto_refresh=True) == "RadarCardPredictive"
    assert card_frame_object_name(mode="statistical", supports_auto_refresh=True) == "RadarCardLive"
    assert card_frame_object_name(mode="statistical", supports_auto_refresh=False) == "RadarCardManual"


def test_kind_badge_presentation() -> None:
    assert kind_badge_presentation("statistical") == ("统计", "RadarCardKindBadgeStatistical")
    assert kind_badge_presentation("predictive") == ("展望", "RadarCardKindBadgePredictive")


def test_mode_badge_presentation() -> None:
    assert mode_badge_presentation(
        supports_auto_refresh=False,
        phase="intraday",
        phase_label="盘中",
    ) == ("手动", "RadarCardModeBadgeOff")
    assert mode_badge_presentation(
        supports_auto_refresh=True,
        phase="intraday",
        phase_label="盘中",
    ) == ("盘中", "RadarCardModeBadgeLive")
    assert mode_badge_presentation(
        supports_auto_refresh=True,
        phase="closed",
        phase_label="收盘",
    ) == ("收盘", "RadarCardModeBadgeOff")


def test_format_card_meta() -> None:
    assert format_card_meta(updated_at_text="", card_resonance=0) == ""
    assert format_card_meta(updated_at_text="更新 10:00", card_resonance=0) == "更新 10:00"
    assert format_card_meta(updated_at_text="更新 10:00", card_resonance=2) == "更新 10:00 · 共振 2"
    assert format_card_meta(updated_at_text="", card_resonance=1) == "共振 1"


def test_count_resonance_hits() -> None:
    counts = {"a": 2, "b": 1, "c": 3}
    assert count_resonance_hits(["a", "b", "c"], counts) == 2
    assert count_resonance_hits(["a", "b", "c"], counts, threshold=3) == 1
    assert count_resonance_hits([], counts) == 0


def test_fallback_visible_card_ids() -> None:
    ids = ["a", "b", "c", "d"]
    assert fallback_visible_card_ids(ids, 2) == ["a", "b"]
    assert fallback_visible_card_ids(ids, 5) == ids
    assert fallback_visible_card_ids([], 2) == []


def test_card_shows_sector_actions() -> None:
    assert card_shows_sector_actions("sector_theme")
    assert card_shows_sector_actions("sector_flow_hot")
    assert not card_shows_sector_actions("leader_pick")


def test_card_shows_add_watchlist_actions() -> None:
    assert not card_shows_add_watchlist_actions("watchlist_intraday")
    assert card_shows_add_watchlist_actions("leader_pick")
