"""板块资金概览：右侧实时榜。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.market.sector_flow import SectorFlowOverviewSeries, SectorFlowOverviewSnapshot
from vnpy_ashare.services.sector_flow import format_sector_net_flow_yi
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color


class SectorFlowOverviewLegend(QtWidgets.QWidget):
    sector_selected = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectorFlowOverviewLegend")
        self.setMinimumWidth(150)
        self.setMaximumWidth(220)
        self._snapshot: SectorFlowOverviewSnapshot | None = None
        self._series: list[SectorFlowOverviewSeries] = []
        self._color_map: dict[str, str] = {}
        self._selected_id = ""

        self._title = QtWidgets.QLabel("主力净流入")
        self._title.setObjectName("SectionLabel")

        self._table = QtWidgets.QTableWidget(self)
        self._table.setObjectName("SectorFlowOverviewLegendTable")
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["板块", "净流入"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.cellClicked.connect(self._on_cell_clicked)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._title)
        layout.addWidget(self._table, stretch=1)

        theme_manager().register_callback(lambda _t: self._table.viewport().update())

    def render_snapshot(self, snapshot: SectorFlowOverviewSnapshot, *, color_map: dict[str, str]) -> None:
        self._snapshot = snapshot
        self._color_map = dict(color_map)
        self._series = sorted(
            list(snapshot.inflow_series) + list(snapshot.outflow_series),
            key=lambda item: item.latest_yi,
            reverse=True,
        )
        self._table.setRowCount(len(self._series))
        for row_index, series in enumerate(self._series):
            name_item = QtWidgets.QTableWidgetItem(series.name)
            name_item.setData(QtCore.Qt.ItemDataRole.UserRole, series.sector_id)
            color = self._color_map.get(series.sector_id, "")
            if color:
                name_item.setForeground(QtGui.QColor(color))
            value_item = QtWidgets.QTableWidgetItem(format_sector_net_flow_yi(series.latest_yi))
            value_item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter))
            value_item.setForeground(QtGui.QColor(pct_change_color(series.latest_yi, theme_manager().tokens())))
            self._table.setItem(row_index, 0, name_item)
            self._table.setItem(row_index, 1, value_item)
        self._table.resizeColumnToContents(0)

    def select_sector(self, sector_id: str) -> None:
        self._selected_id = sector_id
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is None:
                continue
            if str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "") == sector_id:
                self._table.selectRow(row)
                return

    def _on_cell_clicked(self, row: int, _column: int) -> None:
        item = self._table.item(row, 0)
        if item is None:
            return
        sector_id = str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "")
        if sector_id:
            self.sector_selected.emit(sector_id)
