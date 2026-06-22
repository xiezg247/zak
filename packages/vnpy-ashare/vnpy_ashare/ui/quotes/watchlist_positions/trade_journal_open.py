"""独立打开交易流水管理对话框。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.ui.quotes.watchlist_positions.trade_journal_manage_view import TradeJournalManageView


def _localize_close_button(box: QtWidgets.QDialogButtonBox) -> None:
    close_btn = box.button(QtWidgets.QDialogButtonBox.StandardButton.Close)
    if close_btn is not None:
        close_btn.setText("关闭")


def show_trade_journal_manager(
    parent: QtWidgets.QWidget | None = None,
    *,
    days: int = 7,
    side: str | None = None,
    trade_date: str | None = None,
    symbol: str | None = None,
    exchange: str | None = None,
    on_changed: Callable[[], None] | None = None,
) -> None:
    """打开流水明细对话框（风控登记卖出、笔记中心等入口复用）。"""
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle("交易流水")
    dialog.setMinimumSize(720, 480)

    layout = QtWidgets.QVBoxLayout(dialog)
    view = TradeJournalManageView(dialog, initial_days=days, initial_side=side)
    if trade_date:
        day = trade_date[:10]
        view.set_date_range(start_date=day, end_date=day)
    if symbol:
        view.set_symbol_filter(symbol=symbol, exchange=exchange or "")
    layout.addWidget(view, stretch=1)

    if on_changed is not None:
        view.entries_changed.connect(on_changed)

    close_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close, parent=dialog)
    _localize_close_button(close_box)
    close_box.rejected.connect(dialog.reject)
    close_btn = close_box.button(QtWidgets.QDialogButtonBox.StandardButton.Close)
    if close_btn is not None:
        close_btn.clicked.connect(dialog.accept)
    layout.addWidget(close_box)

    view.reload()
    dialog.exec()


def show_today_sell_journal(
    parent: QtWidgets.QWidget | None = None,
    *,
    on_changed: Callable[[], None] | None = None,
) -> None:
    today = datetime.now(CHINA_TZ).date().isoformat()
    show_trade_journal_manager(
        parent,
        side="sell",
        trade_date=today,
        on_changed=on_changed,
    )
