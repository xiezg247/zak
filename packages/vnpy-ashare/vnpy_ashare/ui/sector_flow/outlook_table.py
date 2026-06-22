"""板块未来 N 日资金展望表。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.market.sector_flow import (
    SectorFlowOutlookRow,
    SectorFlowOutlookSnapshot,
    SectorFlowRow,
)
from vnpy_ashare.services.sector_flow_outlook_strategy import classify_sector_resonance
from vnpy_common.ui.data_table import configure_data_table
from vnpy_common.ui.theme.manager import theme_manager

_ROW_HEIGHT = 30


def _format_trade_date_short(trade_date: str) -> str:
    cleaned = str(trade_date or "").strip()
    if len(cleaned) == 8 and cleaned.isdigit():
        return f"{cleaned[4:6]}-{cleaned[6:8]}"
    return cleaned


def _bias_background(bias: str, tokens) -> QtGui.QColor:
    palette = {
        "偏多": tokens.market_rise,
        "偏空": tokens.market_fall,
        "震荡": tokens.text_muted,
    }
    color = QtGui.QColor(palette.get(bias, tokens.text_muted))
    color.setAlpha(56 if bias == "震荡" else 88)
    return color


def _resonance_background(resonance: str, tokens) -> QtGui.QColor:
    palette = {
        "同向": tokens.market_rise,
        "背离": tokens.semantic_warning,
    }
    color = QtGui.QColor(palette.get(resonance, tokens.text_muted))
    color.setAlpha(48)
    return color


class SectorFlowOutlookTable(QtWidgets.QTableWidget):
    sector_activated = QtCore.Signal(str)
    sector_selected = QtCore.Signal(object)
    detail_requested = QtCore.Signal(object)
    sector_strategy_scan_requested = QtCore.Signal(object)
    batch_strategy_scan_requested = QtCore.Signal(list)
    sector_ai_requested = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectorFlowOutlookTable")
        configure_data_table(self, object_name="SectorFlowOutlookTable", alternating=False)
        self._continuation_rows: list[SectorFlowOutlookRow] = []
        self._sector_scans: dict[str, SectorFlowOutlookRow] = {}
        self._forward_dates: tuple[str, ...] = ()
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.customContextMenuRequested.connect(self._show_context_menu)
        theme_manager().register_callback(lambda _t: self.viewport().update())

    def set_continuation_data(
        self,
        snapshot: SectorFlowOutlookSnapshot,
        *,
        rows: list[SectorFlowOutlookRow] | None = None,
        sector_scans: dict[str, SectorFlowOutlookRow] | None = None,
    ) -> None:
        self._forward_dates = snapshot.forward_dates
        self._continuation_rows = list(rows if rows is not None else snapshot.rows)
        self._sector_scans = dict(sector_scans or {})
        self._render(empty_hint=snapshot.empty_hint)

    def set_empty_hint(self, message: str) -> None:
        self._continuation_rows = []
        self._sector_scans = {}
        self._forward_dates = ()
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(["提示"])
        self.setRowCount(1)
        hint = QtWidgets.QTableWidgetItem(message)
        hint.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
        self.setItem(0, 0, hint)

    def selected_sector_rows(self) -> list[SectorFlowRow]:
        row_indexes = sorted({index.row() for index in self.selectedIndexes()})
        rows: list[SectorFlowRow] = []
        for row_index in row_indexes:
            if 0 <= row_index < len(self._continuation_rows):
                rows.append(self._continuation_rows[row_index].sector)
        return rows

    def selected_sector_row(self) -> SectorFlowRow | None:
        selected = self.selected_sector_rows()
        return selected[0] if selected else None

    def selected_outlook_row(self) -> SectorFlowOutlookRow | None:
        row_index = self.currentRow()
        if row_index < 0 or row_index >= len(self._continuation_rows):
            return None
        return self._continuation_rows[row_index]

    def selected_sector_row_at(self, row_index: int) -> SectorFlowRow | None:
        if row_index < 0 or row_index >= len(self._continuation_rows):
            return None
        return self._continuation_rows[row_index].sector

    def focus_sectors(self, sector_ids: set[str]) -> None:
        if not sector_ids:
            return
        model = self.selectionModel()
        if model is None:
            return
        first = True
        for row_index, outlook_row in enumerate(self._continuation_rows):
            if outlook_row.sector.sector_id not in sector_ids:
                continue
            index = self.model().index(row_index, 0)
            flags = QtCore.QItemSelectionModel.SelectionFlag.Rows
            if first:
                model.select(index, flags | QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect)
                first = False
            else:
                model.select(index, flags | QtCore.QItemSelectionModel.SelectionFlag.Select)

    def _render(self, *, empty_hint: str = "") -> None:
        rows = self._continuation_rows
        if not rows:
            self.set_empty_hint(empty_hint or "暂无未来3日展望数据")
            return
        headers = ["名称", "延续模式"]
        for index, trade_date in enumerate(self._forward_dates, start=1):
            headers.append(f"T+{index}({_format_trade_date_short(trade_date)})")
        headers.extend(["强度", "策略T+1", "共振", "说明"])
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setRowCount(len(rows))
        for row_index, outlook_row in enumerate(rows):
            sector_id = outlook_row.sector.sector_id
            scan_row = self._sector_scans.get(sector_id)
            self._set_text_cell(row_index, 0, outlook_row.sector.name)
            self._set_text_cell(row_index, 1, outlook_row.headline_pattern)
            for day_index, day in enumerate(outlook_row.days):
                self._set_bias_cell(row_index, 2 + day_index, day.bias, strength=day.strength)
            strength_col = 2 + len(self._forward_dates)
            first_strength = outlook_row.days[0].strength if outlook_row.days else 0.0
            self._set_text_cell(row_index, strength_col, f"{first_strength:.2f}")
            strategy_col = strength_col + 1
            resonance_col = strength_col + 2
            rationale_col = strength_col + 3
            if scan_row and scan_row.days:
                self._set_bias_cell(
                    row_index,
                    strategy_col,
                    scan_row.days[0].bias,
                    strength=scan_row.days[0].strength,
                )
                resonance = classify_sector_resonance(outlook_row, scan_row)
                self._set_resonance_cell(row_index, resonance_col, resonance)
                rationale = f"{outlook_row.rationale} · 策略：{scan_row.rationale}"
            else:
                self._set_text_cell(row_index, strategy_col, "—")
                self._set_resonance_cell(row_index, resonance_col, "—")
                rationale = outlook_row.rationale
            self._set_text_cell(row_index, rationale_col, rationale)
        self.setColumnWidth(0, 96)
        self.setColumnWidth(1, 88)

    def _set_text_cell(self, row_index: int, col_index: int, text: str) -> None:
        item = QtWidgets.QTableWidgetItem(text)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        self.setItem(row_index, col_index, item)

    def _set_bias_cell(
        self,
        row_index: int,
        col_index: int,
        bias: str,
        *,
        strength: float | None = None,
    ) -> None:
        tokens = theme_manager().tokens()
        label = bias
        if strength is not None and bias != "—":
            label = f"{bias} {strength:.2f}"
        item = QtWidgets.QTableWidgetItem(label)
        item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        item.setBackground(_bias_background(bias, tokens))
        self.setItem(row_index, col_index, item)

    def _set_resonance_cell(self, row_index: int, col_index: int, resonance: str) -> None:
        tokens = theme_manager().tokens()
        item = QtWidgets.QTableWidgetItem(resonance)
        item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        item.setBackground(_resonance_background(resonance, tokens))
        self.setItem(row_index, col_index, item)

    def _on_selection_changed(self) -> None:
        sector = self.selected_sector_row()
        if sector is not None:
            self.sector_selected.emit(sector)

    def _on_cell_double_clicked(self, row: int, _column: int) -> None:
        if row < 0:
            return
        outlook_row = self.selected_outlook_row()
        if outlook_row is not None:
            self.detail_requested.emit(outlook_row)

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        row_index = self.rowAt(pos.y())
        if row_index < 0:
            return
        sector = self.selected_sector_row_at(row_index)
        if sector is None:
            return
        selected = self.selected_sector_rows()
        if sector.sector_id not in {item.sector_id for item in selected}:
            selected = [sector]
        menu = QtWidgets.QMenu(self)
        if len(selected) > 1:
            scan_action = menu.addAction(f"扫描选中 {len(selected)} 个板块")
        else:
            scan_action = menu.addAction("按策略扫描本板块")
        ai_action = menu.addAction("AI 解读本板块")
        detail_action = menu.addAction("查看展望明细")
        drill_action = menu.addAction("市场成分")
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen == scan_action:
            if len(selected) > 1:
                self.batch_strategy_scan_requested.emit(selected)
            else:
                self.sector_strategy_scan_requested.emit(sector)
        elif chosen == ai_action:
            self.sector_ai_requested.emit(sector)
        elif chosen == detail_action:
            self._on_cell_double_clicked(row_index, 0)
        elif chosen == drill_action:
            self.sector_activated.emit(sector.name)
