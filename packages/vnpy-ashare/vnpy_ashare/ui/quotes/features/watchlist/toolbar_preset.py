"""自选页工具栏随工作流预设显隐。"""

from __future__ import annotations

from vnpy_ashare.ui.quotes.features.watchlist.prefs import LayoutPresetId
from vnpy_ashare.ui.quotes.features.watchlist.preset_specs import PRESET_SPECS
from vnpy_ashare.ui.quotes.page.roles import is_strategy_monitor_page
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost


def apply_toolbar_for_preset(page: WatchlistHost, preset_id: LayoutPresetId) -> None:
    if is_strategy_monitor_page(page.page_name):
        return
    spec = PRESET_SPECS[preset_id]
    add_signal = getattr(page, "add_signal_panel_button", None)
    if add_signal is not None and page.config.show_watchlist_signals:
        add_signal.setVisible(spec.show_add_signal_toolbar)
