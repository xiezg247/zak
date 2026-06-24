"""自选页工具栏预设显隐测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

from vnpy_ashare.ui.quotes.features.watchlist.toolbar_preset import apply_toolbar_for_preset


def test_apply_toolbar_for_preset_shows_emotion_on_toolbar() -> None:
    page = MagicMock()
    page.config.show_watchlist_signals = True
    page.config.show_watchlist_positions = False
    chip = MagicMock()
    page.emotion_cycle_chip = chip
    page.add_signal_panel_button = MagicMock()

    apply_toolbar_for_preset(page, "intraday")
    chip.setVisible.assert_called_with(True)

    apply_toolbar_for_preset(page, "review")
    chip.setVisible.assert_called_with(True)
