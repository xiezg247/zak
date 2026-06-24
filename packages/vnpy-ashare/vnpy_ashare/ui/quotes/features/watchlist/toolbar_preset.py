"""自选页工具栏随工作流预设显隐。"""

from __future__ import annotations

from vnpy_ashare.ui.quotes.features.watchlist.prefs import LayoutPresetId
from vnpy_ashare.ui.quotes.features.watchlist.preset_specs import PRESET_SPECS
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost


def _sync_emotion_chip_visibility(page: WatchlistHost, *, visible: bool) -> None:
    emotion = getattr(page, "emotion_cycle_chip", None)
    if emotion is not None:
        emotion.setVisible(visible)


def apply_toolbar_for_preset(page: WatchlistHost, preset_id: LayoutPresetId) -> None:
    spec = PRESET_SPECS[preset_id]
    add_signal = getattr(page, "add_signal_panel_button", None)
    if add_signal is not None and page.config.show_watchlist_signals:
        add_signal.setVisible(spec.show_add_signal_toolbar)
    if page.config.show_watchlist_signals or page.config.show_watchlist_positions:
        _sync_emotion_chip_visibility(page, visible=spec.show_emotion_chips)
