"""自选页工作流布局预设（盘中 / 登记 / 复盘）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences.watchlist_position import save_position_panel_expanded
from vnpy_ashare.config.preferences.watchlist_signal import save_signal_panel_expanded
from vnpy_ashare.ui.quotes.features.watchlist.prefs import LayoutPresetId, save_watchlist_layout_preset
from vnpy_ashare.ui.quotes.watchlist_signals.splitter import apply_center_splitter_sizes

from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost


_PRESET_LABELS: tuple[tuple[LayoutPresetId, str], ...] = (
    ("intraday", "盘中"),
    ("register", "登记"),
    ("review", "复盘"),
)

_PRESET_PANEL_STATE: dict[LayoutPresetId, tuple[bool, bool]] = {
    "intraday": (True, False),
    "register": (True, True),
    "review": (False, True),
}


def layout_preset_options() -> tuple[tuple[LayoutPresetId, str], ...]:
    return _PRESET_LABELS


def apply_layout_preset(page: WatchlistHost, preset_id: LayoutPresetId, *, persist: bool = True) -> None:
    signal_expanded, position_expanded = _PRESET_PANEL_STATE[preset_id]
    signal_panel = getattr(page, "signal_panel", None)
    if signal_panel is not None:
        signal_panel.set_expanded(signal_expanded, emit=True)
        save_signal_panel_expanded(signal_expanded)
    position_panel = getattr(page, "position_panel", None)
    if position_panel is not None:
        position_panel.set_expanded(position_expanded, emit=True)
        save_position_panel_expanded(position_expanded)
    if persist:
        save_watchlist_layout_preset(preset_id)
    apply_center_splitter_sizes(page)
