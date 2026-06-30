"""策略监控页工具栏：不含加入信号区与情绪周期。"""

from __future__ import annotations

from unittest.mock import MagicMock

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.quotes.features.watchlist.toolbar import append_watchlist_strategy_toolbar_actions
from vnpy_ashare.ui.quotes.page.roles import STRATEGY_MONITOR_PAGE


def test_strategy_monitor_toolbar_omits_signal_panel() -> None:
    page = MagicMock()
    page.page_name = STRATEGY_MONITOR_PAGE
    page.config.show_watchlist_signals = True
    page.config.show_watchlist_positions = True
    page.config.show_stock_notes = False
    page.config.show_refresh_quotes_button = False
    page.config.show_batch_backtest_button = False
    page.add_signal_panel_button = MagicMock()

    toolbar = QtWidgets.QHBoxLayout()
    more_actions: list[tuple[str, object]] = []

    append_watchlist_strategy_toolbar_actions(
        page,
        toolbar,
        more_actions,
        policy=None,
        show_backtest_in_toolbar=False,
        show_diagnose_in_toolbar=False,
    )

    page.add_signal_panel_button.assert_not_called()
