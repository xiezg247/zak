"""选股结果表格共用逻辑。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ui.styles import FALL_COLOR, FLAT_COLOR, RISE_COLOR

ROW_DATA_ROLE = QtCore.Qt.ItemDataRole.UserRole


def configure_screener_results_table(table: QtWidgets.QTableWidget) -> None:
    """选股结果表通用配置：勾选列操作，禁用行高亮选中。"""
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
    table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setFixedWidth(0)
    table.setAlternatingRowColors(True)
    table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)


def clear_screener_results_table(table: QtWidgets.QTableWidget) -> None:
    table.setRowCount(0)
    table.setColumnCount(0)
    table.clearSelection()
    table.setCurrentItem(None)


def apply_screener_results_view(
    table: QtWidgets.QTableWidget,
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str]],
    *,
    empty_label: QtWidgets.QLabel | None = None,
) -> None:
    """刷新结果表，并在无数据时展示空状态提示。"""
    if not rows:
        clear_screener_results_table(table)
        table.hide()
        if empty_label is not None:
            empty_label.show()
        return

    populate_screener_results_table(table, rows, columns)
    table.clearSelection()
    table.setCurrentItem(None)
    if empty_label is not None:
        empty_label.hide()
    table.show()


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
    reason_col = next(
        (idx + 1 for idx, (key, _) in enumerate(columns) if key == "hit_reason"),
        None,
    )
    name_col = next(
        (idx + 1 for idx, (key, _) in enumerate(columns) if key == "name"),
        2,
    )
    stretch_col = reason_col if reason_col is not None else name_col
    header.setSectionResizeMode(stretch_col, QtWidgets.QHeaderView.ResizeMode.Stretch)
    for col in range(len(headers)):
        if col not in (0, stretch_col):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

    for row_index, row in enumerate(rows):
        check_item = QtWidgets.QTableWidgetItem()
        check_item.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled)
        check_item.setCheckState(QtCore.Qt.CheckState.Unchecked)
        check_item.setData(ROW_DATA_ROLE, row)
        table.setItem(row_index, 0, check_item)

        for col_index, (key, _label) in enumerate(columns, start=1):
            value = row.get(key, "")
            if isinstance(value, float):
                if key in ("change_pct", "momentum_5d"):
                    text = f"{value:+.2f}"
                elif key in ("similarity_score",):
                    text = f"{value:.1f}"
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
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row_index, col_index, item)

    table.clearSelection()
    table.setCurrentItem(None)


def iter_checked_table_rows(table: QtWidgets.QTableWidget) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_index in range(table.rowCount()):
        item = table.item(row_index, 0)
        if item and item.checkState() == QtCore.Qt.CheckState.Checked:
            data = item.data(ROW_DATA_ROLE)
            if isinstance(data, dict):
                rows.append(data)
    return rows


def all_table_rows_checked(table: QtWidgets.QTableWidget) -> bool:
    if table.rowCount() == 0:
        return False
    for row_index in range(table.rowCount()):
        item = table.item(row_index, 0)
        if item is None or item.checkState() != QtCore.Qt.CheckState.Checked:
            return False
    return True


def select_all_table_rows(table: QtWidgets.QTableWidget) -> None:
    for row_index in range(table.rowCount()):
        item = table.item(row_index, 0)
        if item is not None:
            item.setCheckState(QtCore.Qt.CheckState.Checked)


def toggle_select_all_table_rows(table: QtWidgets.QTableWidget) -> bool:
    """切换全选/取消全选，返回切换后是否已全部选中。"""
    check_all = not all_table_rows_checked(table)
    state = QtCore.Qt.CheckState.Checked if check_all else QtCore.Qt.CheckState.Unchecked
    for row_index in range(table.rowCount()):
        item = table.item(row_index, 0)
        if item is not None:
            item.setCheckState(state)
    return check_all
