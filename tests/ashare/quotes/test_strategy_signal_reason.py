"""策略页信号区「理由」：弹窗展示，不跳转自选。"""

from __future__ import annotations

from unittest.mock import MagicMock

from vnpy_ashare.ui.quotes.features.watchlist_panels import WatchlistPanelsFeature
from vnpy_ashare.ui.quotes.page.roles import STRATEGY_MONITOR_PAGE


def test_strategy_signal_row_activated_shows_reason_dialog() -> None:
    page = MagicMock()
    page.page_name = STRATEGY_MONITOR_PAGE
    page.signal_panel = MagicMock()

    WatchlistPanelsFeature(page).on_strategy_signal_row_activated("600000.SSE")

    page.signal_panel.show_signal_reason.assert_called_once_with("600000.SSE")
