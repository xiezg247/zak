"""共振侧栏常量、过滤与按钮态（无 Qt）。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from vnpy_ashare.quotes.radar.loaders import RadarResonanceEntry
from vnpy_ashare.quotes.radar.radar_snapshot import resonance_entry_to_row_dict
from vnpy_ashare.screener.run.ultra_short_pool_filter import filter_resonance_entries

RadarResonanceTab = Literal["all", "statistical", "predictive"]
ResonanceFilterMode = Literal["all", "dragon_1", "ultra_short"]

RESONANCE_TABS: tuple[tuple[RadarResonanceTab, str], ...] = (
    ("all", "全部"),
    ("statistical", "统计"),
    ("predictive", "展望"),
)

RESONANCE_FILTER_OPTIONS: tuple[tuple[ResonanceFilterMode, str], ...] = (
    ("all", "全部共振"),
    ("dragon_1", "仅龙一"),
    ("ultra_short", "短线主池"),
)

RESONANCE_HANDLE_WIDTH = 24
RESONANCE_COLLAPSED_WIDTH = RESONANCE_HANDLE_WIDTH
RESONANCE_CONTENT_MIN_WIDTH = 220
RESONANCE_CONTENT_MAX_WIDTH = 380
RESONANCE_EXPANDED_MIN_WIDTH = RESONANCE_HANDLE_WIDTH + RESONANCE_CONTENT_MIN_WIDTH
RESONANCE_EXPANDED_DEFAULT_WIDTH = 280
COLLAPSE_BUTTON_SIZE = 20


def resonance_empty_message(tab_key: RadarResonanceTab) -> str:
    if tab_key == "statistical":
        return "暂无统计区共振\n需同时出现在 2 张及以上统计卡"
    if tab_key == "predictive":
        return "暂无展望区共振\n需同时出现在 2 张及以上展望卡"
    return "暂无共振标的\n需同时出现在 2 张及以上卡片"


def format_resonance_stats(
    *,
    resonance_total: int,
    dragon_1_total: int,
    ultra_short_count: int,
) -> str:
    return f"共振 {resonance_total} · 龙一 {dragon_1_total} · 主池 {ultra_short_count}"


def gate_banner_text(*, blocked: bool, emotion_stage_label: str) -> str | None:
    if blocked and emotion_stage_label:
        return f"{emotion_stage_label}：不宜短线新开仓"
    return None


def risk_banner_text(risk_count: int) -> str | None:
    if risk_count > 0:
        return f"炸板断板风险 {risk_count} 只（主池过滤已剔除）"
    return None


def collapse_button_tooltip(expanded: bool) -> str:
    return "收起共振列表" if expanded else "展开共振列表"


def parse_filter_mode(value: object) -> ResonanceFilterMode:
    if value in ("all", "dragon_1", "ultra_short"):
        return value  # type: ignore[return-value]
    return "all"


def build_filter_row_lookup(
    raw_by_tab: Mapping[RadarResonanceTab, tuple[RadarResonanceEntry, ...]],
    row_lookup: Mapping[str, object],
) -> dict[str, object]:
    """为过滤构造 vt → row dict。"""
    lookup: dict[str, object] = {}
    for tab_entries in raw_by_tab.values():
        for entry in tab_entries:
            lookup[entry.vt_symbol] = resonance_entry_to_row_dict(entry, row_lookup)  # type: ignore[arg-type]
    return lookup


def filter_resonance_tab_entries(
    raw: tuple[RadarResonanceEntry, ...],
    *,
    filter_mode: ResonanceFilterMode,
    row_lookup: Mapping[str, object],
    risk_vt_symbols: frozenset[str],
) -> tuple[RadarResonanceEntry, ...]:
    filtered = tuple(filter_resonance_entries(raw, mode=filter_mode, row_lookup=row_lookup))
    if filter_mode == "ultra_short" and risk_vt_symbols:
        filtered = tuple(entry for entry in filtered if entry.vt_symbol not in risk_vt_symbols)
    return filtered


def count_ultra_short_entries(
    raw_all: tuple[RadarResonanceEntry, ...],
    *,
    row_lookup: Mapping[str, object],
    risk_vt_symbols: frozenset[str],
) -> int:
    return len(
        [
            entry
            for entry in filter_resonance_entries(
                raw_all,
                mode="ultra_short",
                row_lookup=row_lookup,
            )
            if entry.vt_symbol not in risk_vt_symbols
        ]
    )


def apply_resonance_filters(
    raw_by_tab: Mapping[RadarResonanceTab, tuple[RadarResonanceEntry, ...]],
    *,
    filter_mode: ResonanceFilterMode,
    row_lookup: Mapping[str, object],
    risk_vt_symbols: frozenset[str],
) -> tuple[dict[RadarResonanceTab, tuple[RadarResonanceEntry, ...]], int]:
    """按当前过滤模式生成各 Tab 列表，并返回主池计数。"""
    lookup = build_filter_row_lookup(raw_by_tab, row_lookup)
    ultra_short_count = count_ultra_short_entries(
        raw_by_tab.get("all", ()),
        row_lookup=lookup,
        risk_vt_symbols=risk_vt_symbols,
    )
    entries_by_tab = {
        tab_key: filter_resonance_tab_entries(
            raw,
            filter_mode=filter_mode,
            row_lookup=lookup,
            risk_vt_symbols=risk_vt_symbols,
        )
        for tab_key, raw in raw_by_tab.items()
    }
    return entries_by_tab, ultra_short_count


@dataclass(frozen=True, slots=True)
class ResonanceActionState:
    add_all_enabled: bool
    dragon_enabled: bool
    focus_enabled: bool
    ai_enabled: bool
    screener_enabled: bool
    leader_enabled: bool
    weights_enabled: bool
    plan_enabled: bool
    eod_enabled: bool
    focus_tooltip: str


def resonance_action_state(
    *,
    has_visible: bool,
    has_any_resonance: bool,
    blocked: bool,
    filter_mode: ResonanceFilterMode,
) -> ResonanceActionState:
    """侧栏操作按钮可用态与短线关注提示。"""
    if not has_visible:
        if has_any_resonance and filter_mode != "all":
            tip = "当前过滤下无标的：可切回「全部共振」或放宽过滤后再写入"
        elif not has_any_resonance:
            tip = "暂无共振标的（需同时出现在 2 张及以上卡片）。请先刷新雷达卡片"
        else:
            tip = "当前 Tab 下无共振标的"
    else:
        tip = "将当前列表写入自选池并加入「短线关注」分组（追加，不覆盖）"
        if blocked:
            tip += "。注：情绪退潮期仍可建观察池，不宜新开仓"

    return ResonanceActionState(
        add_all_enabled=has_visible,
        dragon_enabled=has_visible and not blocked,
        focus_enabled=has_visible,
        ai_enabled=has_visible,
        screener_enabled=has_visible,
        leader_enabled=has_visible and not blocked,
        weights_enabled=True,
        plan_enabled=True,
        eod_enabled=True,
        focus_tooltip=tip,
    )
