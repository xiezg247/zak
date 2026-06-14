"""板块资金行业表格。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.sector_flow import SectorFlowRow
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color

_COL_NAME = 0
_COL_STRENGTH = 1
_COL_CHANGE = 2
_COL_FLOW = 3
_COL_COUNT = 4
_COL_SOURCE = 5

_HEADERS = ("名称", "强度", "涨幅%", "主力净额(亿)", "家数", "口径")
_HEADER_TOOLTIPS: dict[str, str] = {
    "名称": "Tushare 行业；双击跳转市场页并按该行业筛选",
    "强度": "上涨家数占比×100 + 行业平均涨幅，衡量板块热度",
    "涨幅%": "行业成分股平均涨跌幅",
    "主力净额(亿)": "行业成分汇总：优先 Tushare net_mf_amount（多为日频，万元→亿）；缺失时为成交额×涨幅估算",
    "家数": "纳入统计的成分股数量（至少 3 只）",
    "口径": "日频=Tushare 主力；估算=成交额×涨幅",
}


class SectorFlowTable(QtWidgets.QTableWidget):
    sector_activated = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectorFlowTable")
        self.setColumnCount(len(_HEADERS))
        self.setHorizontalHeaderLabels(_HEADERS)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        self.setColumnWidth(_COL_NAME, 140)
        for col, title in enumerate(_HEADERS):
            item = self.horizontalHeaderItem(col)
            if item is None:
                item = QtWidgets.QTableWidgetItem(title)
                self.setHorizontalHeaderItem(col, item)
            tip = _HEADER_TOOLTIPS.get(title, "")
            if tip:
                item.setToolTip(tip)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
        theme_manager().register_callback(lambda _t: self.viewport().update())

    def set_empty_hint(self, message: str) -> None:
        self.setRowCount(1)
        hint = QtWidgets.QTableWidgetItem(message)
        hint.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
        self.setItem(0, _COL_NAME, hint)
        for col in range(1, len(_HEADERS)):
            self.setItem(0, col, QtWidgets.QTableWidgetItem(""))

    def set_rows(self, rows: list[SectorFlowRow]) -> None:
        self.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            name_item = QtWidgets.QTableWidgetItem(row.name)
            name_item.setData(QtCore.Qt.ItemDataRole.UserRole, row.sector_id)
            self.setItem(row_index, _COL_NAME, name_item)

            self.setItem(row_index, _COL_STRENGTH, QtWidgets.QTableWidgetItem(f"{row.strength:.1f}"))

            change_item = QtWidgets.QTableWidgetItem(f"{row.change_pct:+.2f}")
            color = pct_change_color(row.change_pct, theme_manager().tokens())
            change_item.setForeground(QtGui.QColor(color))
            self.setItem(row_index, _COL_CHANGE, change_item)

            flow_item = QtWidgets.QTableWidgetItem(f"{row.net_flow_yi:+.2f}")
            flow_color = pct_change_color(row.net_flow_yi, theme_manager().tokens())
            flow_item.setForeground(QtGui.QColor(flow_color))
            self.setItem(row_index, _COL_FLOW, flow_item)

            self.setItem(row_index, _COL_COUNT, QtWidgets.QTableWidgetItem(str(row.stock_count)))

            source_label = {"proxy": "估算", "tushare": "日频"}.get(row.flow_source, row.flow_source)
            self.setItem(row_index, _COL_SOURCE, QtWidgets.QTableWidgetItem(source_label))

    def focus_sectors(self, sector_ids: set[str]) -> None:
        if not sector_ids:
            return
        first_row: int | None = None
        self.clearSelection()
        for row in range(self.rowCount()):
            name_item = self.item(row, _COL_NAME)
            if name_item is None:
                continue
            sector_id = str(name_item.data(QtCore.Qt.ItemDataRole.UserRole) or "")
            if sector_id not in sector_ids:
                continue
            self.selectRow(row)
            if first_row is None:
                first_row = row
        if first_row is not None:
            self.scrollToItem(self.item(first_row, _COL_NAME))

    def _on_cell_double_clicked(self, row: int, _column: int) -> None:
        name_item = self.item(row, _COL_NAME)
        if name_item is None:
            return
        industry = str(name_item.text() or "").strip()
        if industry:
            self.sector_activated.emit(industry)
