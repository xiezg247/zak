"""策略监控页工具栏：不含加入信号区与情绪周期。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.quotes.features.watchlist.toolbar import append_watchlist_strategy_toolbar_actions
from vnpy_ashare.ui.quotes.page.roles import STRATEGY_MONITOR_PAGE


def test_strategy_monitor_toolbar_omits_signal_and_emotion() -> None:
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

    with patch(
        "vnpy_ashare.ui.quotes.features.watchlist.toolbar.EmotionCycleChip",
    ) as emotion_cls:
        append_watchlist_strategy_toolbar_actions(
            page,
            toolbar,
            more_actions,
            policy=None,
            show_backtest_in_toolbar=False,
            show_diagnose_in_toolbar=False,
        )
        emotion_cls.assert_not_called()

    page.add_signal_panel_button.assert_not_called()
    assert page.emotion_cycle_chip is not page.add_signal_panel_button
