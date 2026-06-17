"""市场页板块筛选与账户交易上限联动。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.config.trading_universe import (
    default_market_board_label,
    is_market_board_combo_locked,
    market_board_combo_labels,
    market_board_label_to_filter,
    trading_boards_hint,
)

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


def configure_market_board_combo(combo: QtWidgets.QComboBox) -> str | None:
    """按账户可交易板块配置下拉，并返回初始 ``_market_board`` 值。"""
    labels = market_board_combo_labels()
    default_label = default_market_board_label()
    locked = is_market_board_combo_locked()

    combo.blockSignals(True)
    combo.clear()
    combo.addItems(list(labels))
    index = combo.findText(default_label)
    if index >= 0:
        combo.setCurrentIndex(index)
    combo.setEnabled(not locked)
    hint = trading_boards_hint()
    if locked:
        combo.setToolTip(f"账户可交易板块：{default_label}")
    elif hint:
        combo.setToolTip(f"账户可交易：{hint}")
    else:
        combo.setToolTip("")
    combo.blockSignals(False)
    return market_board_label_to_filter(combo.currentText())


def sync_page_market_board(page: QuotesPage, *, invalidate_cache: bool = True) -> None:
    """将下拉当前项同步到 ``page._market_board``。"""
    if not page.config.show_board_filter:
        return
    page._market_board = market_board_label_to_filter(page.board_combo.currentText())
    if invalidate_cache:
        page._market_board_base = None
        page._market_board_base_key = None


def reset_market_board_combo_to_default(page: QuotesPage) -> None:
    """恢复市场页默认板块（账户受限时保持沪深主板等默认值）。"""
    if not page.config.show_board_filter:
        return
    default_label = default_market_board_label()
    combo = page.board_combo
    combo.blockSignals(True)
    index = combo.findText(default_label)
    if index >= 0:
        combo.setCurrentIndex(index)
    combo.blockSignals(False)
    sync_page_market_board(page)
