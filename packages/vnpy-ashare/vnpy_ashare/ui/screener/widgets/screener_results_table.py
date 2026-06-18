"""选股结果表格共用逻辑。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.quotes.market.moneyflow_kind import flow_kind_label
from vnpy_common.ui.scroll_area import style_market_table_scroll_bars
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color

ScreeningTableRow = ScreenerResultRow

ROW_DATA_ROLE = QtCore.Qt.ItemDataRole.UserRole
_SORT_ROLE = QtCore.Qt.ItemDataRole.UserRole + 2

_DISPLAY_HIDDEN_KEYS = frozenset({"vt_symbol", "source"})
_LEFT_ALIGN_KEYS = frozenset({"name", "hit_reason", "industry"})
_CENTER_ALIGN_KEYS = frozenset({"symbol", "diff_status", "flow_kind"})
_PERCENT_KEYS = frozenset({"change_pct", "turnover_rate", "momentum_5d"})
_SIGNED_PERCENT_KEYS = frozenset({"change_pct", "momentum_5d"})
_NUMERIC_SORT_KEYS = frozenset(
    {
        "change_pct",
        "momentum_5d",
        "turnover_rate",
        "last_price",
        "close",
        "pe_ttm",
        "pb",
        "total_mv",
        "circ_mv",
        "net_mf_amount",
        "volume",
        "volume_ratio",
        "composite_score",
        "similarity_score",
        "buy_elg_amount",
        "sell_elg_amount",
    }
)

_SCREENER_ROW_HEIGHT = 30


_ParentIndex = QtCore.QModelIndex | QtCore.QPersistentModelIndex


class ScreenerResultsTableDelegate(QtWidgets.QStyledItemDelegate):
    """选股结果表：强制垂直居中，避免 QSS padding 导致内容贴顶。"""

    def initStyleOption(
        self,
        option: QtWidgets.QStyleOptionViewItem,
        index: _ParentIndex,
    ) -> None:
        super().initStyleOption(option, index)
        view_option = cast(Any, option)
        horizontal = view_option.displayAlignment & QtCore.Qt.AlignmentFlag.AlignHorizontal_Mask
        view_option.displayAlignment = horizontal | QtCore.Qt.AlignmentFlag.AlignVCenter


def configure_screener_results_table(table: QtWidgets.QTableWidget) -> None:
    """选股结果表通用配置：勾选列 + 排序 + 行高。"""
    table.setObjectName("ScreenerResultsTable")
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
    table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(_SCREENER_ROW_HEIGHT)
    table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setItemDelegate(ScreenerResultsTableDelegate(table))

    style_market_table_scroll_bars(table)
    header = table.horizontalHeader()
    if hasattr(header, "setStretchHighlightSections"):
        header.setStretchHighlightSections(False)


def _display_columns(columns: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(key, label) for key, label in columns if key not in _DISPLAY_HIDDEN_KEYS]


def _format_cell_text(key: str, value: Any) -> str:
    if value is None or value == "":
        return "—"
    if key == "flow_kind":
        return flow_kind_label(str(value))
    if isinstance(value, float):
        if key in _SIGNED_PERCENT_KEYS:
            return f"{value:+.2f}%"
        if key in _PERCENT_KEYS:
            return f"{value:.2f}%"
        if key == "similarity_score":
            return f"{value:.1f}"
        if key == "composite_score":
            return f"{value:.1f}"
        if key in ("last_price", "close", "pb", "pe_ttm"):
            return f"{value:.2f}"
        if key in ("total_mv", "circ_mv", "net_mf_amount", "volume", "buy_elg_amount", "sell_elg_amount"):
            return f"{value:,.0f}"
        return f"{value:.2f}"
    text = str(value).strip()
    return text or "—"


def _cell_alignment(key: str) -> QtCore.Qt.AlignmentFlag:
    if key in _LEFT_ALIGN_KEYS:
        return QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
    if key in _CENTER_ALIGN_KEYS:
        return QtCore.Qt.AlignmentFlag.AlignCenter
    return QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter


def _apply_cell_style(item: QtWidgets.QTableWidgetItem, key: str, value: Any, *, tokens) -> None:
    text = item.text()
    if key in _SIGNED_PERCENT_KEYS and isinstance(value, (int, float)):
        item.setForeground(QtGui.QColor(pct_change_color(float(value), tokens)))
        return
    if key == "momentum_5d" and isinstance(value, (int, float)):
        item.setForeground(QtGui.QColor(pct_change_color(float(value), tokens)))
        return
    if key == "net_mf_amount" and isinstance(value, (int, float)):
        item.setForeground(QtGui.QColor(pct_change_color(float(value), tokens)))
        return
    if key == "diff_status":
        if text == "新增":
            item.setForeground(QtGui.QColor(pct_change_color(3.0, tokens)))
        elif text in ("移除", "剔除"):
            item.setForeground(QtGui.QColor(pct_change_color(-3.0, tokens)))
        elif text in ("持续", "不变"):
            item.setForeground(QtGui.QColor(tokens.text_muted))
        return
    if key == "composite_score" and isinstance(value, (int, float)) and float(value) >= 80:
        item.setForeground(QtGui.QColor(tokens.accent))


def clear_screener_results_table(table: QtWidgets.QTableWidget) -> None:
    table.setSortingEnabled(False)
    table.setRowCount(0)
    table.setColumnCount(0)
    table.clearSelection()
    table.setSortingEnabled(True)


def apply_screener_results_view(
    table: QtWidgets.QTableWidget,
    rows: Sequence[ScreeningTableRow],
    columns: list[tuple[str, str]],
    *,
    empty_label: QtWidgets.QLabel | None = None,
    select_all_btn: QtWidgets.QPushButton | None = None,
    result_action_bar: QtWidgets.QWidget | None = None,
    export_btn: QtWidgets.QPushButton | None = None,
) -> None:
    """刷新结果表，并在无数据时展示空状态提示。"""
    has_results = bool(rows)
    if result_action_bar is not None and hasattr(result_action_bar, "set_has_results"):
        result_action_bar.set_has_results(has_results)
    if export_btn is not None:
        export_btn.setEnabled(has_results)
    if not rows:
        clear_screener_results_table(table)
        table.hide()
        if empty_label is not None:
            empty_label.show()
        update_select_all_button(table, select_all_btn)
        return

    populate_screener_results_table(table, rows, columns)
    table.clearSelection()
    if empty_label is not None:
        empty_label.hide()
    table.show()
    update_select_all_button(table, select_all_btn)


def populate_screener_results_table(
    table: QtWidgets.QTableWidget,
    rows: Sequence[ScreeningTableRow],
    columns: list[tuple[str, str]],
) -> None:
    display_columns = _display_columns(columns)
    headers = ["选择", "#"] + [label for _, label in display_columns]
    table.setSortingEnabled(False)
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))

    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
    table.setColumnWidth(0, 36)
    header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Fixed)
    table.setColumnWidth(1, 40)
    reason_col = next(
        (idx + 2 for idx, (key, _) in enumerate(display_columns) if key == "hit_reason"),
        None,
    )
    name_col = next(
        (idx + 2 for idx, (key, _) in enumerate(display_columns) if key == "name"),
        3,
    )
    stretch_col = reason_col if reason_col is not None else name_col
    header.setSectionResizeMode(stretch_col, QtWidgets.QHeaderView.ResizeMode.Stretch)
    for col in range(len(headers)):
        if col not in (0, 1, stretch_col):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

    tokens = theme_manager().tokens()
    muted = QtGui.QColor(tokens.text_muted)
    for row_index, row in enumerate(rows):
        check_item = QtWidgets.QTableWidgetItem()
        check_item.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled)
        check_item.setCheckState(QtCore.Qt.CheckState.Unchecked)
        check_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        check_item.setData(ROW_DATA_ROLE, row)
        table.setItem(row_index, 0, check_item)

        rank_item = QtWidgets.QTableWidgetItem(str(row_index + 1))
        rank_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        rank_item.setForeground(muted)
        rank_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
        rank_item.setData(_SORT_ROLE, row_index + 1)
        table.setItem(row_index, 1, rank_item)

        for col_index, (key, _label) in enumerate(display_columns, start=2):
            value = row.get(key, "")
            text = _format_cell_text(key, value)
            item = QtWidgets.QTableWidgetItem(text)
            item.setTextAlignment(_cell_alignment(key))
            if key in _NUMERIC_SORT_KEYS and isinstance(value, (int, float)):
                item.setData(_SORT_ROLE, float(value))
            if key in ("hit_reason", "name", "industry") and text not in ("", "—"):
                item.setToolTip(text)
            _apply_cell_style(item, key, value, tokens=tokens)
            table.setItem(row_index, col_index, item)

    table.clearSelection()
    table.setSortingEnabled(True)


def iter_checked_table_rows(table: QtWidgets.QTableWidget) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_index in range(table.rowCount()):
        item = table.item(row_index, 0)
        if item and item.checkState() == QtCore.Qt.CheckState.Checked:
            data = item.data(ROW_DATA_ROLE)
            if isinstance(data, dict):
                rows.append(data)
            elif hasattr(data, "to_dict"):
                rows.append(data.to_dict())
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
                item.setCheckState(QtCore.Qt.CheckState.Checked if row_index in selected_rows else QtCore.Qt.CheckState.Unchecked)
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
