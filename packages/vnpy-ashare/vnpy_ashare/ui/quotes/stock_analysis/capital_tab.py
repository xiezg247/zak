"""个股分析：资金面 Tab。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.services.stock_analysis_context import MoneyflowDayRow, MoneyflowProfile
from vnpy_common.ui.data_table import configure_data_table
from vnpy_common.ui.panel_widgets import MetricTile, content_card, hint_label, section_title, tab_page
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color


def _fmt_amount(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1e4:
        return f"{value / 1e4:.1f}万"
    return f"{value:,.0f}"


class CapitalAnalysisTab(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = hint_label("")
        self._net_tile = MetricTile("主力净流入", subtitle="最新交易日")
        self._buy_tile = MetricTile("超大单买入")
        self._sell_tile = MetricTile("超大单卖出")

        metrics = QtWidgets.QHBoxLayout()
        metrics.setSpacing(10)
        for tile in (self._net_tile, self._buy_tile, self._sell_tile):
            metrics.addWidget(tile, stretch=1)
        metrics_wrap = QtWidgets.QWidget()
        metrics_wrap.setLayout(metrics)

        self._table = QtWidgets.QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["日期", "主力净流入", "超大单买", "超大单卖"])
        configure_data_table(self._table)

        page = tab_page(
            self._status,
            content_card(metrics_wrap, margins=(8, 8, 8, 8)),
            content_card(section_title("近 15 交易日"), self._table),
            stretch_index=2,
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(page)

    def show_idle(self, message: str = "切换到本 Tab 时加载资金流") -> None:
        self._status.setText(message)
        self._net_tile.set_value("—")
        self._buy_tile.set_value("—")
        self._sell_tile.set_value("—")
        self._table.setRowCount(0)

    def show_loading(self, message: str = "正在加载资金流…") -> None:
        self._status.setText(message)
        for tile in (self._net_tile, self._buy_tile, self._sell_tile):
            tile.set_value("…")
        self._table.setRowCount(0)

    def show_profile(self, profile: MoneyflowProfile | None) -> None:
        if profile is None or (not profile.history and profile.latest is None):
            self._status.setText(profile.message if profile and profile.message else "暂无资金流数据")
            self._net_tile.set_value("—")
            self._buy_tile.set_value("—")
            self._sell_tile.set_value("—")
            self._table.setRowCount(0)
            return

        latest = profile.latest or (profile.history[0] if profile.history else None)
        if latest is not None:
            color = pct_change_color(latest.net_mf_amount or 0, theme_manager().tokens())
            self._net_tile.set_value(_fmt_amount(latest.net_mf_amount), color=color)
            self._buy_tile.set_value(_fmt_amount(latest.buy_elg_amount))
            self._sell_tile.set_value(_fmt_amount(latest.sell_elg_amount))
            self._status.setText(f"数据日期 {latest.trade_date or '—'} · 单位：万元")
        else:
            self._status.setText(profile.message or "暂无资金流")

        self._fill_history(profile.history)

    def _fill_history(self, rows: list[MoneyflowDayRow]) -> None:
        self._table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            values = [
                row.trade_date,
                _fmt_amount(row.net_mf_amount),
                _fmt_amount(row.buy_elg_amount),
                _fmt_amount(row.sell_elg_amount),
            ]
            for col_idx, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                if col_idx > 0:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row_idx, col_idx, item)
        self._table.resizeColumnsToContents()
