"""只读数据表配置（滚动条 + objectName）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_common.ui.scroll_area import style_table_scroll_bars

DATA_TABLE_NAME = "DataTable"
PIVOT_TABLE_NAME = "PivotTable"


def configure_data_table(
    table: QtWidgets.QTableWidget,
    *,
    object_name: str = DATA_TABLE_NAME,
    alternating: bool = True,
    select_rows: bool = True,
) -> QtWidgets.QTableWidget:
    table.setObjectName(object_name)
    table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(alternating)
    if select_rows:
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.setShowGrid(False)
    table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    style_table_scroll_bars(table)
    return table
