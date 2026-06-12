"""个股分析：股东结构 Tab。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.services.stock.holders import HolderProfile
from vnpy_common.ui.data_table import configure_data_table
from vnpy_common.ui.panel_widgets import MetricTile, content_card, hint_label, section_title, tab_page


def _fmt_amount(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1e8:
        return f"{value / 1e8:.2f}亿"
    if abs(value) >= 1e4:
        return f"{value / 1e4:.1f}万"
    return f"{value:,.0f}"


class HoldersAnalysisTab(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = hint_label("")
        self._period_tile = MetricTile("报告期")
        self._count_tile = MetricTile("股东数", subtitle="十大流通/股东")

        metrics = QtWidgets.QHBoxLayout()
        metrics.addWidget(self._period_tile, stretch=1)
        metrics.addWidget(self._count_tile, stretch=1)
        metrics_wrap = QtWidgets.QWidget()
        metrics_wrap.setLayout(metrics)

        self._table = QtWidgets.QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["股东名称", "持股数量", "持股比例", "公告日"])
        configure_data_table(self._table)

        page = tab_page(
            self._status,
            content_card(metrics_wrap, margins=(8, 8, 8, 8)),
            content_card(section_title("十大股东"), self._table),
            stretch_index=2,
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(page)

    def show_idle(self, message: str = "切换到本 Tab 时加载股东结构") -> None:
        self._status.setText(message)
        self._period_tile.set_value("—")
        self._count_tile.set_value("—")
        self._table.setRowCount(0)

    def show_loading(self, message: str = "正在加载股东结构…") -> None:
        self._status.setText(message)
        self._period_tile.set_value("…")
        self._count_tile.set_value("…")
        self._table.setRowCount(0)

    def show_profile(self, profile: HolderProfile | None) -> None:
        if profile is None:
            self.show_idle("暂无股东数据")
            return

        holders = profile.holders
        self._period_tile.set_value(profile.end_date or "—")
        self._count_tile.set_value(str(len(holders)))
        self._status.setText(profile.message or f"共 {len(holders)} 条股东记录")

        self._table.setRowCount(len(holders))
        for row_idx, row in enumerate(holders):
            values = [
                str(row.get("holder_name") or "—"),
                _fmt_amount(row.get("hold_amount")),
                f"{row['hold_ratio']:.2f}%" if isinstance(row.get("hold_ratio"), (int, float)) else "—",
                str(row.get("ann_date") or "—"),
            ]
            for col_idx, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                if col_idx > 0:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row_idx, col_idx, item)
        self._table.resizeColumnsToContents()
