"""选股结果表格共用逻辑。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ui.styles import FALL_COLOR, FLAT_COLOR, RISE_COLOR

ROW_DATA_ROLE = QtCore.Qt.ItemDataRole.UserRole


def populate_screener_results_table(
    table: QtWidgets.QTableWidget,
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str]],
) -> None:
    headers = ["选择"] + [label for _, label in columns]
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))

    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
    name_col = next(
        (idx + 1 for idx, (key, _) in enumerate(columns) if key == "name"),
        2,
    )
    header.setSectionResizeMode(name_col, QtWidgets.QHeaderView.ResizeMode.Stretch)
    for col in range(len(headers)):
        if col not in (0, name_col):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

    for row_index, row in enumerate(rows):
        check_item = QtWidgets.QTableWidgetItem()
        check_item.setFlags(
            QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled
        )
        check_item.setCheckState(QtCore.Qt.CheckState.Unchecked)
        check_item.setData(ROW_DATA_ROLE, row)
        table.setItem(row_index, 0, check_item)

        for col_index, (key, _label) in enumerate(columns, start=1):
            value = row.get(key, "")
            if isinstance(value, float):
                if key in ("change_pct",):
                    text = f"{value:+.2f}"
                elif key in ("last_price", "close", "pb", "pe_ttm"):
                    text = f"{value:.2f}"
                elif key in ("total_mv", "circ_mv", "net_mf_amount", "volume"):
                    text = f"{value:,.0f}"
                else:
                    text = f"{value:.2f}"
            else:
                text = str(value)
            item = QtWidgets.QTableWidgetItem(text)
            item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if key == "change_pct":
                change_pct = float(value or 0)
                color = RISE_COLOR if change_pct > 0 else FALL_COLOR if change_pct < 0 else FLAT_COLOR
                item.setForeground(QtGui.QColor(color))
            elif key == "hit_reason":
                item.setTextAlignment(
                    QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
                )
            table.setItem(row_index, col_index, item)


def iter_checked_table_rows(table: QtWidgets.QTableWidget) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_index in range(table.rowCount()):
        item = table.item(row_index, 0)
        if item and item.checkState() == QtCore.Qt.CheckState.Checked:
            data = item.data(ROW_DATA_ROLE)
            if isinstance(data, dict):
                rows.append(data)
    return rows


def select_all_table_rows(table: QtWidgets.QTableWidget) -> None:
    for row_index in range(table.rowCount()):
        item = table.item(row_index, 0)
        if item is not None:
            item.setCheckState(QtCore.Qt.CheckState.Checked)
