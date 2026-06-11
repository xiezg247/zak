"""选股结果表格共用逻辑。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color

ROW_DATA_ROLE = QtCore.Qt.ItemDataRole.UserRole


def configure_screener_results_table(table: QtWidgets.QTableWidget) -> None:
    """选股结果表通用配置：勾选列 + 行选中高亮（与自选页 MarketTable 一致）。"""
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
    table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setFixedWidth(0)
    table.setAlternatingRowColors(True)


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
    select_all_btn: QtWidgets.QPushButton | None = None,
) -> None:
    """刷新结果表，并在无数据时展示空状态提示。"""
    if not rows:
        clear_screener_results_table(table)
        table.hide()
        if empty_label is not None:
            empty_label.show()
        update_select_all_button(table, select_all_btn)
        return

    populate_screener_results_table(table, rows, columns)
    table.clearSelection()
    table.setCurrentItem(None)
    if empty_label is not None:
        empty_label.hide()
    table.show()
    update_select_all_button(table, select_all_btn)


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
                color = pct_change_color(change_pct, theme_manager().tokens())
                item.setForeground(QtGui.QColor(color))
            elif key == "hit_reason":
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            elif key == "diff_status" and text == "新增":
                item.setForeground(QtGui.QColor(pct_change_color(3.0, theme_manager().tokens())))
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


def update_select_all_button(table: QtWidgets.QTableWidget, button: QtWidgets.QPushButton | None) -> None:
    """根据勾选状态更新「全选 / 取消全选」按钮文案。"""
    if button is None:
        return
    if table.rowCount() == 0:
        button.setText("全选")
        return
    button.setText("取消全选" if all_table_rows_checked(table) else "全选")


def select_all_table_rows(table: QtWidgets.QTableWidget) -> None:
    toggle_select_all_table_rows(table, select_all=True)


def toggle_select_all_table_rows(
    table: QtWidgets.QTableWidget,
    *,
    select_all: bool | None = None,
) -> bool:
    """切换全选/取消全选，返回切换后是否已全部选中。"""
    check_all = not all_table_rows_checked(table) if select_all is None else select_all
    state = QtCore.Qt.CheckState.Checked if check_all else QtCore.Qt.CheckState.Unchecked
    table.blockSignals(True)
    try:
        for row_index in range(table.rowCount()):
            item = table.item(row_index, 0)
            if item is not None:
                item.setCheckState(state)
        if check_all:
            table.selectAll()
        else:
            table.clearSelection()
    finally:
        table.blockSignals(False)
    return check_all


def wire_screener_results_table(
    table: QtWidgets.QTableWidget,
    *,
    select_all_btn: QtWidgets.QPushButton | None = None,
) -> None:
    """连接勾选列与行选中双向同步，并维护全选按钮文案。"""
    sync_state = {"active": False}

    def on_selection_changed() -> None:
        if sync_state["active"]:
            return
        sync_state["active"] = True
        table.blockSignals(True)
        try:
            selected_rows = {index.row() for index in table.selectionModel().selectedRows()}
            for row_index in range(table.rowCount()):
                item = table.item(row_index, 0)
                if item is None:
                    continue
                item.setCheckState(
                    QtCore.Qt.CheckState.Checked
                    if row_index in selected_rows
                    else QtCore.Qt.CheckState.Unchecked
                )
        finally:
            table.blockSignals(False)
            sync_state["active"] = False
        update_select_all_button(table, select_all_btn)

    def on_item_changed(item: QtWidgets.QTableWidgetItem) -> None:
        if sync_state["active"] or item.column() != 0:
            return
        sync_state["active"] = True
        try:
            row_index = item.row()
            index = table.model().index(row_index, 0)
            selection_model = table.selectionModel()
            if selection_model is None:
                return
            mode = (
                QtCore.QItemSelectionModel.SelectionFlag.Select
                if item.checkState() == QtCore.Qt.CheckState.Checked
                else QtCore.QItemSelectionModel.SelectionFlag.Deselect
            )
            selection_model.select(
                index,
                mode | QtCore.QItemSelectionModel.SelectionFlag.Rows,
            )
        finally:
            sync_state["active"] = False
        update_select_all_button(table, select_all_btn)

    table.itemSelectionChanged.connect(on_selection_changed)
    table.itemChanged.connect(on_item_changed)
