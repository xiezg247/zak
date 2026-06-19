"""板块资金行业表格。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.market.sector_flow import SectorFlowRow
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color

_COL_NAME = 0
_COL_STRENGTH = 1
_COL_CHANGE = 2
_COL_FLOW = 3
_COL_RATE = 4
_COL_LEADER = 5
_COL_COUNT = 6
_COL_SOURCE = 7

_HEADERS_INTRADAY = ("名称", "强度", "涨幅%", "主力净额(亿)", "家数", "口径")
_HEADERS_OFFICIAL = ("名称", "强度", "涨幅%", "主力净额(亿)", "净占比%", "龙头", "家数", "口径")

_HEADER_TOOLTIPS: dict[str, str] = {
    "名称": "双击查看市场页行业成分（主力净流入榜）",
    "强度": "上涨家数占比×100 + 行业平均涨幅，或日终涨跌幅+净占比合成",
    "涨幅%": "板块涨跌幅",
    "主力净额(亿)": "行业成分汇总或官方板块主力净流入（亿元）",
    "净占比%": "东财官方主力净流入占板块成交额比例",
    "龙头": "板块领涨或主力净流入最大股",
    "家数": "纳入统计的成分股数量",
    "口径": "数据来源与更新频率",
}

_SOURCE_LABELS = {
    "proxy": "估算",
    "tushare": "日频",
    "dc_industry": "东财",
    "dc_concept": "东财",
    "ths_concept": "同花顺",
    "sw_dc": "申万+东财",
    "sw": "申万",
}


class SectorFlowTable(QtWidgets.QTableWidget):
    sector_activated = QtCore.Signal(str)
    sector_selected = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectorFlowTable")
        self._official_mode = False
        self._divergence_mode = False
        self._rows: list[SectorFlowRow] = []
        self._apply_headers()
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        self.setColumnWidth(_COL_NAME, 120)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        theme_manager().register_callback(lambda _t: self.viewport().update())

    def set_divergence_mode(self, enabled: bool) -> None:
        self._divergence_mode = enabled
        self._apply_headers()

    def set_official_mode(self, official: bool) -> None:
        if self._official_mode == official:
            return
        self._official_mode = official
        self._apply_headers()

    def _apply_headers(self) -> None:
        headers: tuple[str, ...]
        if self._divergence_mode:
            headers = ("名称", "背离", "涨幅%", "主力净额(亿)", "强度")
        elif self._official_mode:
            headers = _HEADERS_OFFICIAL
        else:
            headers = _HEADERS_INTRADAY
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        for col, title in enumerate(headers):
            item = self.horizontalHeaderItem(col)
            if item is None:
                item = QtWidgets.QTableWidgetItem(title)
                self.setHorizontalHeaderItem(col, item)
            tip = _HEADER_TOOLTIPS.get(title, "")
            if tip:
                item.setToolTip(tip)

    def set_empty_hint(self, message: str) -> None:
        self.setRowCount(1)
        hint = QtWidgets.QTableWidgetItem(message)
        hint.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
        self.setItem(0, _COL_NAME, hint)
        for col in range(1, self.columnCount()):
            self.setItem(0, col, QtWidgets.QTableWidgetItem(""))

    def set_rows(self, rows: list[SectorFlowRow]) -> None:
        self._rows = list(rows)
        self.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            name_item = QtWidgets.QTableWidgetItem(row.name)
            name_item.setData(QtCore.Qt.ItemDataRole.UserRole, row.sector_id)
            self.setItem(row_index, _COL_NAME, name_item)

            if self._divergence_mode:
                self.setItem(row_index, 1, QtWidgets.QTableWidgetItem(row.divergence_kind or "—"))
                change_item = QtWidgets.QTableWidgetItem(f"{row.change_pct:+.2f}")
                color = pct_change_color(row.change_pct, theme_manager().tokens())
                change_item.setForeground(QtGui.QColor(color))
                self.setItem(row_index, 2, change_item)
                flow_item = QtWidgets.QTableWidgetItem(f"{row.net_flow_yi:+.2f}")
                flow_color = pct_change_color(row.net_flow_yi, theme_manager().tokens())
                flow_item.setForeground(QtGui.QColor(flow_color))
                self.setItem(row_index, 3, flow_item)
                self.setItem(row_index, 4, QtWidgets.QTableWidgetItem(f"{row.strength:.1f}"))
                continue

            self.setItem(row_index, _COL_STRENGTH, QtWidgets.QTableWidgetItem(f"{row.strength:.1f}"))

            change_item = QtWidgets.QTableWidgetItem(f"{row.change_pct:+.2f}")
            color = pct_change_color(row.change_pct, theme_manager().tokens())
            change_item.setForeground(QtGui.QColor(color))
            self.setItem(row_index, _COL_CHANGE, change_item)

            flow_item = QtWidgets.QTableWidgetItem(f"{row.net_flow_yi:+.2f}")
            flow_color = pct_change_color(row.net_flow_yi, theme_manager().tokens())
            flow_item.setForeground(QtGui.QColor(flow_color))
            self.setItem(row_index, _COL_FLOW, flow_item)

            if self._official_mode:
                rate_item = QtWidgets.QTableWidgetItem(f"{row.net_flow_rate:+.2f}" if row.net_flow_rate else "—")
                self.setItem(row_index, _COL_RATE, rate_item)
                self.setItem(row_index, _COL_LEADER, QtWidgets.QTableWidgetItem(row.leader_stock or "—"))
                count_text = str(row.stock_count) if row.stock_count else "—"
                self.setItem(row_index, _COL_COUNT, QtWidgets.QTableWidgetItem(count_text))
                source_col = _COL_SOURCE
            else:
                self.setItem(row_index, 4, QtWidgets.QTableWidgetItem(str(row.stock_count)))
                source_col = 5

            source_label = _SOURCE_LABELS.get(row.flow_source, row.flow_source)
            self.setItem(row_index, source_col, QtWidgets.QTableWidgetItem(source_label))

    def selected_sector_row(self) -> SectorFlowRow | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if row_index < 0 or row_index >= len(self._rows):
            return None
        return self._rows[row_index]

    def selected_industry(self) -> str:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return ""
        row = selected[0].row()
        name_item = self.item(row, _COL_NAME)
        if name_item is None:
            return ""
        return str(name_item.text() or "").strip()

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
            name = str(name_item.text() or "").strip()
            if sector_id not in sector_ids and name not in sector_ids:
                continue
            self.selectRow(row)
            if first_row is None:
                first_row = row
        if first_row is not None:
            item = self.item(first_row, _COL_NAME)
            if item is not None:
                self.scrollToItem(item)

    def _on_cell_double_clicked(self, row: int, _column: int) -> None:
        name_item = self.item(row, _COL_NAME)
        if name_item is None:
            return
        industry = str(name_item.text() or "").strip()
        if industry:
            self.sector_activated.emit(industry)

    def _on_selection_changed(self) -> None:
        row = self.selected_sector_row()
        if row is not None:
            self.sector_selected.emit(row)
