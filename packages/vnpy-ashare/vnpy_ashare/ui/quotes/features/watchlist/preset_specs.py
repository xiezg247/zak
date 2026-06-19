"""自选页工作流预设规格（与 UI 应用逻辑解耦）。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.ui.quotes.features.watchlist.prefs import LayoutPresetId

POSITION_FOCUS_TABLE_RATIO = 0.25


@dataclass(frozen=True)
class LayoutPresetSpec:
    """单套预设：面板折叠 + 默认 Tab + 视图 + 工具栏显隐。"""

    signal_expanded: bool
    position_expanded: bool
    select_observation_group: bool
    select_all_group: bool
    force_table_view: bool
    show_register_toolbar: bool
    show_add_signal_toolbar: bool
    show_emotion_risk_chips: bool = True
    splitter_table_ratio: float | None = None


PRESET_SPECS: dict[LayoutPresetId, LayoutPresetSpec] = {
    "intraday": LayoutPresetSpec(
        signal_expanded=True,
        position_expanded=False,
        select_observation_group=True,
        select_all_group=False,
        force_table_view=True,
        show_register_toolbar=False,
        show_add_signal_toolbar=True,
    ),
    "register": LayoutPresetSpec(
        signal_expanded=True,
        position_expanded=True,
        select_observation_group=False,
        select_all_group=False,
        force_table_view=False,
        show_register_toolbar=True,
        show_add_signal_toolbar=True,
    ),
    "review": LayoutPresetSpec(
        signal_expanded=False,
        position_expanded=True,
        select_observation_group=False,
        select_all_group=False,
        force_table_view=False,
        show_register_toolbar=True,
        show_add_signal_toolbar=False,
        show_emotion_risk_chips=False,
        splitter_table_ratio=0.4,
    ),
}

PRESET_LABELS: tuple[tuple[LayoutPresetId, str], ...] = (
    ("intraday", "盘中"),
    ("register", "登记"),
    ("review", "复盘"),
)

PRESET_PANEL_STATE: dict[LayoutPresetId, tuple[bool, bool]] = {
    preset_id: (spec.signal_expanded, spec.position_expanded) for preset_id, spec in PRESET_SPECS.items()
}
