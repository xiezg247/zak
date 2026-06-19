"""板块近 N 日资金轮动矩阵表。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.market.sector_flow import SectorFlowRotationRow, SectorFlowRotationSnapshot, SectorFlowRow
from vnpy_common.ui.data_table import configure_data_table
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color

_COL_NAME = 0
_COL_PATTERN = 1
_COL_CUMULATIVE = 2
_COL_MOMENTUM = 3
_COL_DATE_START = 4

_FIXED_HEADERS = ("名称", "方向", "15日累计", "动量Δ")
_DATE_COL_WIDTH = 50
_ROW_HEIGHT = 30

_PATTERN_TIPS = {
    "持续流入": "近15日多数交易日净流入，且近5日动量强于前10日",
    "持续流出": "近15日多数交易日净流出，且累计为负",
    "先出后入": "前半段净流出、后半段转为净流入",
    "先入后出": "前半段净流入、后半段转为净流出",
    "震荡": "流向反复，无明显单边趋势",
}


def _format_trade_date_short(trade_date: str) -> str:
    cleaned = str(trade_date or "").strip()
    if len(cleaned) == 8 and cleaned.isdigit():
        return f"{cleaned[4:6]}-{cleaned[6:8]}"
    if len(cleaned) >= 5 and "-" in cleaned:
        return cleaned[-5:]
    return cleaned


def _format_flow_compact(net_flow_yi: float) -> str:
    if abs(net_flow_yi) < 0.05:
        return "·"
    return f"{net_flow_yi:+.1f}"


def _flow_cell_background(net_flow_yi: float, max_abs: float, tokens) -> QtGui.QColor:
    if abs(net_flow_yi) < 0.05:
        return QtGui.QColor(tokens.table_bg)
    if max_abs <= 0:
        max_abs = 1.0
    ratio = min(abs(net_flow_yi) / max_abs, 1.0)
    base = QtGui.QColor(tokens.market_rise if net_flow_yi >= 0 else tokens.market_fall)
    alpha = int(56 + ratio * 168)
    base.setAlpha(max(0, min(alpha, 255)))
    return base


def _flow_cell_foreground(net_flow_yi: float, max_abs: float, tokens) -> QtGui.QColor:
    if abs(net_flow_yi) < 0.05:
        return QtGui.QColor(tokens.text_muted)
    if max_abs <= 0:
        max_abs = 1.0
    ratio = abs(net_flow_yi) / max_abs
    if ratio >= 0.28:
        return QtGui.QColor("#FFFFFF")
    return QtGui.QColor(tokens.text_primary)


def _pattern_background(pattern: str, tokens) -> QtGui.QColor:
    palette = {
        "持续流入": tokens.market_rise,
        "持续流出": tokens.market_fall,
        "先出后入": tokens.accent,
        "先入后出": tokens.semantic_warning,
        "震荡": tokens.text_muted,
    }
    color = QtGui.QColor(palette.get(pattern, tokens.text_muted))
    color.setAlpha(42)
    return color


class SectorFlowRotationTable(QtWidgets.QTableWidget):
    sector_activated = QtCore.Signal(str)
    sector_selected = QtCore.Signal(object)
    detail_requested = QtCore.Signal(object)
    sector_strategy_scan_requested = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectorFlowRotationTable")
        configure_data_table(self, object_name="SectorFlowRotationTable", alternating=False)
        self._rows: list[SectorFlowRotationRow] = []
        self._trade_dates: tuple[str, ...] = ()
        self._max_abs = 1.0
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setDefaultSectionSize(_DATE_COL_WIDTH)
        header.setMinimumSectionSize(42)
        self.setColumnWidth(_COL_NAME, 96)
        self.setColumnWidth(_COL_PATTERN, 76)
        self.setColumnWidth(_COL_CUMULATIVE, 72)
        self.setColumnWidth(_COL_MOMENTUM, 60)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.customContextMenuRequested.connect(self._show_context_menu)
        theme_manager().register_callback(lambda _t: self.viewport().update())

    def set_empty_hint(self, message: str) -> None:
        self._rows = []
        self._trade_dates = ()
        self.setColumnCount(len(_FIXED_HEADERS))
        self.setHorizontalHeaderLabels(list(_FIXED_HEADERS))
        self.setRowCount(1)
        hint = QtWidgets.QTableWidgetItem(message)
        hint.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
        self.setItem(0, _COL_NAME, hint)

    def apply_snapshot(self, snapshot: SectorFlowRotationSnapshot) -> None:
        self.set_rotation_data(snapshot.trade_dates, list(snapshot.rows), empty_hint=snapshot.empty_hint)

    def set_rotation_data(
        self,
        trade_dates: tuple[str, ...],
        rows: list[SectorFlowRotationRow],
        *,
        empty_hint: str = "",
    ) -> None:
        self._rows = list(rows)
        self._trade_dates = tuple(trade_dates)
        if not self._rows:
            self.set_empty_hint(empty_hint or "暂无近15日轮动数据")
            return

        headers = list(_FIXED_HEADERS) + [_format_trade_date_short(date) for date in self._trade_dates]
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        for col, title in enumerate(headers):
            item = self.horizontalHeaderItem(col)
            if item is None:
                item = QtWidgets.QTableWidgetItem(title)
                self.setHorizontalHeaderItem(col, item)
            if col >= _COL_DATE_START:
                full_date = self._trade_dates[col - _COL_DATE_START]
                item.setToolTip(full_date)

        values = [point.net_flow_yi for row in self._rows for point in row.points]
        self._max_abs = max((abs(value) for value in values), default=1.0)
        if self._max_abs <= 0:
            self._max_abs = 1.0

        tokens = theme_manager().tokens()
        self.setRowCount(len(self._rows))
        for row_index, rotation_row in enumerate(self._rows):
            sector = rotation_row.sector
            name_item = QtWidgets.QTableWidgetItem(sector.name)
            name_item.setData(QtCore.Qt.ItemDataRole.UserRole, sector.sector_id)
            name_item.setToolTip(sector.name)
            self.setItem(row_index, _COL_NAME, name_item)

            pattern_item = QtWidgets.QTableWidgetItem(rotation_row.flow_pattern)
            pattern_item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignCenter))
            pattern_item.setBackground(_pattern_background(rotation_row.flow_pattern, tokens))
            pattern_item.setToolTip(_PATTERN_TIPS.get(rotation_row.flow_pattern, ""))
            self.setItem(row_index, _COL_PATTERN, pattern_item)

            cumulative_item = QtWidgets.QTableWidgetItem(f"{rotation_row.cumulative_net_yi:+.1f}")
            cumulative_item.setForeground(QtGui.QColor(pct_change_color(rotation_row.cumulative_net_yi, tokens)))
            cumulative_item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignCenter))
            self.setItem(row_index, _COL_CUMULATIVE, cumulative_item)

            momentum_item = QtWidgets.QTableWidgetItem(f"{rotation_row.momentum_delta:+.1f}")
            momentum_item.setForeground(QtGui.QColor(pct_change_color(rotation_row.momentum_delta, tokens)))
            momentum_item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignCenter))
            self.setItem(row_index, _COL_MOMENTUM, momentum_item)

            for date_index, point in enumerate(rotation_row.points):
                col = _COL_DATE_START + date_index
                cell = QtWidgets.QTableWidgetItem(_format_flow_compact(point.net_flow_yi))
                cell.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignCenter))
                cell.setBackground(_flow_cell_background(point.net_flow_yi, self._max_abs, tokens))
                cell.setForeground(_flow_cell_foreground(point.net_flow_yi, self._max_abs, tokens))
                cell.setToolTip(f"{_format_trade_date_short(point.trade_date)} 主力 {point.net_flow_yi:+.2f}亿")
                self.setItem(row_index, col, cell)

        self.resizeColumnToContents(_COL_NAME)

    def selected_rotation_row(self) -> SectorFlowRotationRow | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if row_index < 0 or row_index >= len(self._rows):
            return None
        return self._rows[row_index]

    def selected_sector_row(self) -> SectorFlowRow | None:
        rotation_row = self.selected_rotation_row()
        if rotation_row is None:
            return None
        return rotation_row.sector

    def rotation_row_at(self, row_index: int) -> SectorFlowRotationRow | None:
        if row_index < 0 or row_index >= len(self._rows):
            return None
        return self._rows[row_index]

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

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self.itemAt(pos)
        if item is None:
            return
        rotation_row = self.rotation_row_at(item.row())
        if rotation_row is None:
            return
        self.selectRow(item.row())
        menu = QtWidgets.QMenu(self)
        scan_action = menu.addAction("按策略扫描本板块")
        detail_action = menu.addAction("查看资金明细")
        market_action = menu.addAction("市场成分")
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen == scan_action:
            self.sector_strategy_scan_requested.emit(rotation_row.sector)
        elif chosen is detail_action:
            self.detail_requested.emit(rotation_row)
        elif chosen is market_action:
            self.sector_activated.emit(rotation_row.sector.name)

    def _on_cell_double_clicked(self, row: int, _column: int) -> None:
        rotation_row = self.rotation_row_at(row)
        if rotation_row is not None:
            self.detail_requested.emit(rotation_row)

    def _on_selection_changed(self) -> None:
        row = self.selected_sector_row()
        if row is not None:
            self.sector_selected.emit(row)
