"""板块未来 N 日资金展望表。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.market.sector_flow import (
    SectorFlowOutlookCompareRow,
    SectorFlowOutlookRow,
    SectorFlowOutlookSnapshot,
    SectorFlowRow,
)
from vnpy_common.ui.data_table import configure_data_table
from vnpy_common.ui.theme.manager import theme_manager

_MODE_COMPARE = "compare"
_MODE_CONTINUATION = "continuation"
_MODE_STRATEGY = "strategy"

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


def _agreement_background(agreement: str, tokens) -> QtGui.QColor:
    palette = {
        "一致": tokens.market_rise,
        "分歧": tokens.semantic_warning,
        "仅延续": tokens.accent,
        "仅策略": tokens.accent,
    }
    color = QtGui.QColor(palette.get(agreement, tokens.text_muted))
    color.setAlpha(48)
    return color


class SectorFlowOutlookTable(QtWidgets.QTableWidget):
    sector_activated = QtCore.Signal(str)
    sector_selected = QtCore.Signal(object)
    detail_requested = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectorFlowOutlookTable")
        configure_data_table(self, object_name="SectorFlowOutlookTable", alternating=False)
        self._mode = _MODE_COMPARE
        self._compare_rows: list[SectorFlowOutlookCompareRow] = []
        self._continuation_rows: list[SectorFlowOutlookRow] = []
        self._strategy_rows: list[SectorFlowOutlookRow] = []
        self._forward_dates: tuple[str, ...] = ()
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.customContextMenuRequested.connect(self._show_context_menu)
        theme_manager().register_callback(lambda _t: self.viewport().update())

    def set_mode(self, mode: str) -> None:
        self._mode = mode if mode in {_MODE_COMPARE, _MODE_CONTINUATION, _MODE_STRATEGY} else _MODE_COMPARE
        self._render()

    def set_compare_data(
        self,
        forward_dates: tuple[str, ...],
        rows: list[SectorFlowOutlookCompareRow],
        *,
        empty_hint: str = "",
    ) -> None:
        self._forward_dates = forward_dates
        self._compare_rows = list(rows)
        self._mode = _MODE_COMPARE
        self._render(empty_hint=empty_hint)

    def set_continuation_data(
        self,
        snapshot: SectorFlowOutlookSnapshot,
        *,
        rows: list[SectorFlowOutlookRow] | None = None,
    ) -> None:
        self._forward_dates = snapshot.forward_dates
        self._continuation_rows = list(rows if rows is not None else snapshot.rows)
        self._mode = _MODE_CONTINUATION
        self._render(empty_hint=snapshot.empty_hint)

    def set_strategy_data(
        self,
        snapshot: SectorFlowOutlookSnapshot,
        *,
        rows: list[SectorFlowOutlookRow] | None = None,
    ) -> None:
        self._forward_dates = snapshot.forward_dates
        self._strategy_rows = list(rows if rows is not None else snapshot.rows)
        self._mode = _MODE_STRATEGY
        self._render(empty_hint=snapshot.empty_hint)

    def set_empty_hint(self, message: str) -> None:
        self._compare_rows = []
        self._continuation_rows = []
        self._strategy_rows = []
        self._forward_dates = ()
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(["提示"])
        self.setRowCount(1)
        hint = QtWidgets.QTableWidgetItem(message)
        hint.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
        self.setItem(0, 0, hint)

    def selected_sector_row(self) -> SectorFlowRow | None:
        row_index = self.currentRow()
        if row_index < 0:
            return None
        if self._mode == _MODE_COMPARE:
            if row_index >= len(self._compare_rows):
                return None
            return self._compare_rows[row_index].sector
        rows = self._continuation_rows if self._mode == _MODE_CONTINUATION else self._strategy_rows
        if row_index >= len(rows):
            return None
        return rows[row_index].sector

    def selected_compare_row(self) -> SectorFlowOutlookCompareRow | None:
        row_index = self.currentRow()
        if row_index < 0 or row_index >= len(self._compare_rows):
            return None
        return self._compare_rows[row_index]

    def selected_outlook_row(self) -> SectorFlowOutlookRow | None:
        row_index = self.currentRow()
        if row_index < 0:
            return None
        rows = self._continuation_rows if self._mode == _MODE_CONTINUATION else self._strategy_rows
        if row_index >= len(rows):
            return None
        return rows[row_index]

    def focus_sectors(self, sector_ids: set[str]) -> None:
        if not sector_ids:
            return
        for row_index in range(self.rowCount()):
            sector = self.selected_sector_row_at(row_index)
            if sector is not None and sector.sector_id in sector_ids:
                self.selectRow(row_index)
                return

    def selected_sector_row_at(self, row_index: int) -> SectorFlowRow | None:
        if self._mode == _MODE_COMPARE:
            if row_index < 0 or row_index >= len(self._compare_rows):
                return None
            return self._compare_rows[row_index].sector
        rows = self._continuation_rows if self._mode == _MODE_CONTINUATION else self._strategy_rows
        if row_index < 0 or row_index >= len(rows):
            return None
        return rows[row_index].sector

    def _render(self, *, empty_hint: str = "") -> None:
        if self._mode == _MODE_COMPARE:
            self._render_compare(empty_hint=empty_hint)
        elif self._mode == _MODE_CONTINUATION:
            self._render_single(self._continuation_rows, headline_header="延续模式", empty_hint=empty_hint)
        else:
            self._render_single(self._strategy_rows, headline_header="策略摘要", empty_hint=empty_hint)

    def _render_compare(self, *, empty_hint: str = "") -> None:
        if not self._compare_rows:
            self.set_empty_hint(empty_hint or "暂无未来3日展望对照数据")
            return
        headers = ["名称", "一致性"]
        for index, trade_date in enumerate(self._forward_dates, start=1):
            short = _format_trade_date_short(trade_date)
            headers.extend([f"A·T+{index}({short})", f"B·T+{index}({short})"])
        headers.append("延续模式")
        headers.append("策略摘要")
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setRowCount(len(self._compare_rows))
        tokens = theme_manager().tokens()
        for row_index, compare_row in enumerate(self._compare_rows):
            self._set_text_cell(row_index, 0, compare_row.sector.name)
            self._set_bias_cell(row_index, 1, compare_row.agreement, kind="agreement")
            col = 2
            for day_index in range(len(self._forward_dates)):
                cont_day = (
                    compare_row.continuation.days[day_index]
                    if compare_row.continuation and day_index < len(compare_row.continuation.days)
                    else None
                )
                strat_day = (
                    compare_row.strategy.days[day_index]
                    if compare_row.strategy and day_index < len(compare_row.strategy.days)
                    else None
                )
                self._set_bias_cell(row_index, col, cont_day.bias if cont_day else "—")
                self._set_bias_cell(row_index, col + 1, strat_day.bias if strat_day else "—")
                col += 2
            cont_pattern = compare_row.continuation.headline_pattern if compare_row.continuation else "—"
            strat_pattern = compare_row.strategy.headline_pattern if compare_row.strategy else "—"
            self._set_text_cell(row_index, col, cont_pattern)
            self._set_text_cell(row_index, col + 1, strat_pattern)
        self.setColumnWidth(0, 96)
        self.setColumnWidth(1, 64)

    def _render_single(
        self,
        rows: list[SectorFlowOutlookRow],
        *,
        headline_header: str,
        empty_hint: str,
    ) -> None:
        if not rows:
            self.set_empty_hint(empty_hint or "暂无未来3日展望数据")
            return
        headers = ["名称", headline_header]
        for index, trade_date in enumerate(self._forward_dates, start=1):
            headers.append(f"T+{index}({_format_trade_date_short(trade_date)})")
        headers.extend(["强度", "说明"])
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setRowCount(len(rows))
        for row_index, outlook_row in enumerate(rows):
            self._set_text_cell(row_index, 0, outlook_row.sector.name)
            self._set_text_cell(row_index, 1, outlook_row.headline_pattern)
            for day_index, day in enumerate(outlook_row.days):
                self._set_bias_cell(row_index, 2 + day_index, day.bias, strength=day.strength)
            strength_col = 2 + len(self._forward_dates)
            first_strength = outlook_row.days[0].strength if outlook_row.days else 0.0
            self._set_text_cell(row_index, strength_col, f"{first_strength:.2f}")
            self._set_text_cell(row_index, strength_col + 1, outlook_row.rationale)
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
        kind: str = "bias",
    ) -> None:
        tokens = theme_manager().tokens()
        label = bias
        if strength is not None and bias != "—":
            label = f"{bias} {strength:.2f}"
        item = QtWidgets.QTableWidgetItem(label)
        item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        if kind == "agreement":
            item.setBackground(_agreement_background(bias, tokens))
        else:
            item.setBackground(_bias_background(bias, tokens))
        self.setItem(row_index, col_index, item)

    def _on_selection_changed(self) -> None:
        sector = self.selected_sector_row()
        if sector is not None:
            self.sector_selected.emit(sector)

    def _on_cell_double_clicked(self, row: int, _column: int) -> None:
        if row < 0:
            return
        if self._mode == _MODE_COMPARE:
            compare_row = self.selected_compare_row()
            if compare_row is not None:
                self.detail_requested.emit(compare_row)
            return
        outlook_row = self.selected_outlook_row()
        if outlook_row is not None:
            self.detail_requested.emit(outlook_row)

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        row_index = self.rowAt(pos.y())
        if row_index < 0:
            return
        menu = QtWidgets.QMenu(self)
        detail_action = menu.addAction("查看展望明细")
        drill_action = menu.addAction("市场成分")
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen == detail_action:
            self._on_cell_double_clicked(row_index, 0)
        elif chosen == drill_action:
            sector = self.selected_sector_row_at(row_index)
            if sector is not None:
                self.sector_activated.emit(sector.name)
