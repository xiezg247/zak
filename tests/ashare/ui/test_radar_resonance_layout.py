"""共振侧栏布局纯函数。"""

from __future__ import annotations

from vnpy_ashare.quotes.radar.loaders import RadarResonanceEntry
from vnpy_ashare.ui.quotes.radar.resonance_layout import (
    apply_resonance_filters,
    collapse_button_tooltip,
    format_resonance_stats,
    gate_banner_text,
    parse_filter_mode,
    resonance_action_state,
    resonance_empty_message,
    risk_banner_text,
)


def _entry(vt: str, *, card_count: int = 2, leader_tier: str = "") -> RadarResonanceEntry:
    return RadarResonanceEntry(
        vt_symbol=vt,
        name=vt,
        symbol=vt.split(".")[0],
        card_count=card_count,
        card_titles=("卡A", "卡B"),
        price=10.0,
        change_pct=1.0,
        leader_tier=leader_tier,
    )


def test_resonance_empty_message() -> None:
    assert "统计" in resonance_empty_message("statistical")
    assert "展望" in resonance_empty_message("predictive")
    assert "共振标的" in resonance_empty_message("all")


def test_format_and_banners() -> None:
    assert format_resonance_stats(resonance_total=3, dragon_1_total=1, ultra_short_count=2) == (
        "共振 3 · 龙一 1 · 主池 2"
    )
    assert gate_banner_text(blocked=True, emotion_stage_label="退潮") == "退潮：不宜短线新开仓"
    assert gate_banner_text(blocked=False, emotion_stage_label="退潮") is None
    assert risk_banner_text(2) is not None and "2" in risk_banner_text(2)  # type: ignore[operator]
    assert risk_banner_text(0) is None
    assert collapse_button_tooltip(True) == "收起共振列表"
    assert collapse_button_tooltip(False) == "展开共振列表"


def test_parse_filter_mode() -> None:
    assert parse_filter_mode("dragon_1") == "dragon_1"
    assert parse_filter_mode("nope") == "all"


def test_resonance_action_state() -> None:
    empty = resonance_action_state(
        has_visible=False,
        has_any_resonance=False,
        blocked=False,
        filter_mode="all",
    )
    assert not empty.focus_enabled
    assert "暂无共振" in empty.focus_tooltip

    filtered = resonance_action_state(
        has_visible=False,
        has_any_resonance=True,
        blocked=False,
        filter_mode="ultra_short",
    )
    assert "过滤" in filtered.focus_tooltip

    visible_blocked = resonance_action_state(
        has_visible=True,
        has_any_resonance=True,
        blocked=True,
        filter_mode="all",
    )
    assert visible_blocked.focus_enabled
    assert not visible_blocked.dragon_enabled
    assert not visible_blocked.leader_enabled
    assert "退潮" in visible_blocked.focus_tooltip or "不宜" in visible_blocked.focus_tooltip


def test_apply_resonance_filters_all_mode() -> None:
    raw = {
        "all": (_entry("600000.SSE"), _entry("600001.SSE", leader_tier="dragon_1")),
        "statistical": (_entry("600000.SSE"),),
        "predictive": (),
    }
    entries, ultra = apply_resonance_filters(
        raw,
        filter_mode="all",
        row_lookup={},
        risk_vt_symbols=frozenset(),
    )
    assert len(entries["all"]) == 2
    assert len(entries["statistical"]) == 1
    assert ultra >= 0
