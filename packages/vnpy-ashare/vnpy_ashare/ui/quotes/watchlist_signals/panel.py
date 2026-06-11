"""自选页独立策略信号区域。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.signal_snapshot import (
    SIGNAL_DISCLAIMER,
    SignalSnapshot,
    signal_cell_color,
    signal_cell_text,
    signal_missing_kline,
    signal_row_sort_key,
)
from vnpy_ashare.ui.quotes.watchlist_signals.settings import (
    SIGNAL_PANEL_MAX_SYMBOLS,
    WatchlistSignalConfig,
    load_signal_panel_enabled,
    load_signal_panel_expanded,
    load_signal_panel_symbols,
    normalize_signal_panel_symbols,
    save_signal_panel_enabled,
    save_signal_panel_expanded,
    save_signal_panel_symbols,
)
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import market_colors

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

_PANEL_COLUMNS = (
    ("symbol", "代码"),
    ("name", "名称"),
    ("signal", "信号"),
    ("ref_buy_price", "参考买价"),
    ("ref_sell_price", "参考卖价"),
    ("signal_strength", "强度"),
)

_DETAIL_COLUMN_KEYS = ("signal_date", "dist_buy_pct", "signal_reason")

_EMPTY_LIST_TEXT = (
    f"暂无监控标的。请在上方自选表多选后点击「加入信号区」（最多 {SIGNAL_PANEL_MAX_SYMBOLS} 只）。"
)
_FILTER_EMPTY_TEXT = "当前筛选无匹配标的，再次点击统计项可取消筛选。"


class WatchlistSignalPanel(QtWidgets.QWidget):
    """自选页信号监控区：手动名单 + 双均线策略 + 独立表格。"""

    symbols_changed = QtCore.Signal()
    enabled_changed = QtCore.Signal(bool)
    config_changed = QtCore.Signal()
    refresh_requested = QtCore.Signal()
    row_activated = QtCore.Signal(str)
    row_selected = QtCore.Signal(str)
    expansion_changed = QtCore.Signal(bool)

    def __init__(self, page: QuotesPage) -> None:
        super().__init__(page)
        self._page = page
        self._symbols: list[str] = load_signal_panel_symbols()
        self._updated_at = ""
        self._building = False
        self._expanded = load_signal_panel_expanded()
        self._signal_filter: str | None = None
        self._rendered_symbols: list[str] = []
        self._suppress_selection_signal = False

        self.setObjectName("WatchlistSignalPanel")
        theme_manager().bind_stylesheet(self)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)

        self._toggle = QtWidgets.QCheckBox("启用信号", self)
        self._toggle.setChecked(load_signal_panel_enabled())
        self._toggle.toggled.connect(self._on_enabled_toggled)

        self._strategy_label = QtWidgets.QLabel("双均线", self)
        self._strategy_label.setObjectName("SectionLabel")

        self._fast_spin = QtWidgets.QSpinBox(self)
        self._fast_spin.setRange(2, 60)
        self._fast_spin.setPrefix("快 ")
        self._fast_spin.setValue(page.signal_config.fast_window)

        self._slow_spin = QtWidgets.QSpinBox(self)
        self._slow_spin.setRange(3, 120)
        self._slow_spin.setPrefix("慢 ")
        self._slow_spin.setValue(page.signal_config.slow_window)

        self._remove_button = QtWidgets.QPushButton("移出", self)
        self._remove_button.setObjectName("SecondaryButton")
        self._remove_button.clicked.connect(self._on_remove_clicked)

        self._clear_button = QtWidgets.QPushButton("清空", self)
        self._clear_button.setObjectName("SecondaryButton")
        self._clear_button.clicked.connect(self._on_clear_clicked)

        self._refresh_button = QtWidgets.QPushButton("刷新", self)
        self._refresh_button.setObjectName("SecondaryButton")
        self._refresh_button.clicked.connect(self.refresh_requested.emit)

        self._collapse_button = QtWidgets.QToolButton(self)
        self._collapse_button.setCheckable(True)
        self._collapse_button.setChecked(self._expanded)
        self._collapse_button.setArrowType(QtCore.Qt.ArrowType.DownArrow if self._expanded else QtCore.Qt.ArrowType.RightArrow)
        self._collapse_button.clicked.connect(self._on_collapse_toggled)

        header.addWidget(self._collapse_button)
        header.addWidget(QtWidgets.QLabel("策略信号", self))
        header.addWidget(self._toggle)
        header.addStretch()
        header.addWidget(self._strategy_label)
        header.addWidget(self._fast_spin)
        header.addWidget(self._slow_spin)
        header.addWidget(self._remove_button)
        header.addWidget(self._clear_button)
        header.addWidget(self._refresh_button)
        root.addLayout(header)

        self._stats_label = QtWidgets.QLabel("", self)
        self._stats_label.setObjectName("StatsLabel")
        self._stats_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self._stats_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextBrowserInteraction)
        self._stats_label.setOpenExternalLinks(False)
        self._stats_label.linkActivated.connect(self._on_stats_filter_link)
        root.addWidget(self._stats_label)

        self._table = QtWidgets.QTableWidget(self)
        self._table.setObjectName("WatchlistSignalTable")
        self._table.setColumnCount(len(_PANEL_COLUMNS))
        self._table.setHorizontalHeaderLabels([label for _, label in _PANEL_COLUMNS])
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setMinimumHeight(120)
        header_view = self._table.horizontalHeader()
        header_view.setStretchLastSection(True)
        header_view.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self._table.cellDoubleClicked.connect(self._on_cell_activated)
        self._table.itemSelectionChanged.connect(self._on_table_selection_changed)
        root.addWidget(self._table, stretch=1)

        self._empty_label = QtWidgets.QLabel(_EMPTY_LIST_TEXT, self)
        self._empty_label.setObjectName("BottomBarMeta")
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        root.addWidget(self._empty_label)

        self._disclaimer_label = QtWidgets.QLabel(SIGNAL_DISCLAIMER, self)
        self._disclaimer_label.setObjectName("BottomBarMeta")
        self._disclaimer_label.setWordWrap(True)
        root.addWidget(self._disclaimer_label)

        self._fast_spin.valueChanged.connect(self._emit_config_changed)
        self._slow_spin.valueChanged.connect(self._emit_config_changed)

        self._body_widgets = (
            self._stats_label,
            self._table,
            self._empty_label,
            self._disclaimer_label,
            self._strategy_label,
            self._fast_spin,
            self._slow_spin,
            self._remove_button,
            self._clear_button,
            self._refresh_button,
        )
        self._apply_expanded(self._expanded, emit=False)
        self._apply_enabled(self._toggle.isChecked())
        self.render()

    @property
    def symbols(self) -> list[str]:
        return list(self._symbols)

    @property
    def enabled(self) -> bool:
        return self._toggle.isChecked()

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        if self._expanded == expanded:
            self._sync_collapse_button()
            return
        self._expanded = expanded
        self._apply_expanded(expanded, emit=emit)

    def read_config(self) -> WatchlistSignalConfig:
        fast = int(self._fast_spin.value())
        slow = int(self._slow_spin.value())
        if slow <= fast:
            slow = fast + 1
            self._slow_spin.blockSignals(True)
            self._slow_spin.setValue(slow)
            self._slow_spin.blockSignals(False)
        return WatchlistSignalConfig(
            class_name=self._page.signal_config.class_name,
            fast_window=fast,
            slow_window=slow,
        ).normalized()

    def apply_config(self, config: WatchlistSignalConfig) -> None:
        item = config.normalized()
        self._fast_spin.blockSignals(True)
        self._slow_spin.blockSignals(True)
        self._fast_spin.setValue(item.fast_window)
        self._slow_spin.setValue(item.slow_window)
        self._fast_spin.blockSignals(False)
        self._slow_spin.blockSignals(False)

    def set_symbols(self, symbols: list[str], *, save: bool = True) -> None:
        self._symbols = normalize_signal_panel_symbols(symbols)
        if save:
            save_signal_panel_symbols(self._symbols)
        if not self._symbols:
            self._signal_filter = None
        self.render()

    def add_symbols(self, vt_symbols: list[str]) -> tuple[int, int]:
        """返回 (新增数量, 因已达上限未加入数量)。"""
        added = 0
        skipped = 0
        for vt in vt_symbols:
            text = str(vt or "").strip()
            if not text or text in self._symbols:
                continue
            if len(self._symbols) >= SIGNAL_PANEL_MAX_SYMBOLS:
                skipped += 1
                continue
            self._symbols.append(text)
            added += 1
        if added:
            save_signal_panel_symbols(self._symbols)
            self.render()
            self.symbols_changed.emit()
        return added, skipped

    def remove_symbols(self, vt_symbols: list[str]) -> int:
        removed = 0
        for vt in vt_symbols:
            text = str(vt or "").strip()
            if text and text in self._symbols:
                self._symbols.remove(text)
                removed += 1
        if removed:
            save_signal_panel_symbols(self._symbols)
            if not self._symbols:
                self._signal_filter = None
            self.render()
            self.symbols_changed.emit()
        return removed

    def remove_selected_symbols(self) -> int:
        return self.remove_symbols(self.selected_vt_symbols())

    def remove_with_fallback(self, fallback_vt: str | None = None) -> int:
        removed = self.remove_selected_symbols()
        if removed:
            return removed
        fallback = str(fallback_vt or "").strip()
        if fallback:
            return self.remove_symbols([fallback])
        return 0

    def set_updated_at(self, text: str) -> None:
        self._updated_at = text.strip()
        self._refresh_stats()

    def render(self) -> None:
        has_symbols = bool(self._symbols)
        display_symbols = self._sorted_display_symbols()
        if not has_symbols:
            self._rendered_symbols = []
            self._table.setVisible(False)
            self._empty_label.setText(_EMPTY_LIST_TEXT)
            self._empty_label.setVisible(self._expanded)
            self._table.setRowCount(0)
            self._refresh_stats()
            return

        if not display_symbols:
            self._rendered_symbols = []
            self._table.setVisible(False)
            self._empty_label.setText(_FILTER_EMPTY_TEXT)
            self._empty_label.setVisible(self._expanded)
            self._table.setRowCount(0)
            self._refresh_stats()
            return

        self._empty_label.setVisible(False)
        self._table.setVisible(self._expanded)
        if display_symbols == self._rendered_symbols:
            self._update_row_cells(display_symbols)
        else:
            self._rebuild_table(display_symbols)
            self._rendered_symbols = list(display_symbols)
        self._sync_highlight_from_page()
        self._refresh_stats()

    def highlight_symbol(self, vt_symbol: str | None) -> None:
        target = (vt_symbol or "").strip()
        if target and target not in self._symbols:
            target = ""
        self._suppress_selection_signal = True
        try:
            if not target:
                self._table.clearSelection()
                return
            for row in range(self._table.rowCount()):
                item = self._table.item(row, 0)
                if item is None:
                    continue
                vt = str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "")
                if vt == target:
                    self._table.selectRow(row)
                    return
            self._table.clearSelection()
        finally:
            self._suppress_selection_signal = False

    def _sync_highlight_from_page(self) -> None:
        item = self._page.current_item
        if item is None:
            return
        if item.vt_symbol in self._symbols:
            self.highlight_symbol(item.vt_symbol)

    def selected_vt_symbols(self) -> list[str]:
        rows = self._table.selectionModel().selectedRows()
        symbols: list[str] = []
        for model_index in rows:
            item = self._table.item(model_index.row(), 0)
            if item is None:
                continue
            vt = str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "")
            if vt:
                symbols.append(vt)
        return symbols

    def _sorted_display_symbols(self) -> list[str]:
        symbols = self._filtered_symbols()
        return sorted(
            symbols,
            key=lambda vt: signal_row_sort_key(self._page.signal_cache.get(vt)),
            reverse=True,
        )

    def _rebuild_table(self, display_symbols: list[str]) -> None:
        page = self._page
        colors = market_colors(theme_manager().tokens())
        warning_color = theme_manager().tokens().semantic_warning
        self._building = True
        self._table.setRowCount(len(display_symbols))
        for row, vt_symbol in enumerate(display_symbols):
            self._fill_row(row, vt_symbol, colors=colors, warning_color=warning_color, page=page)
        self._building = False

    def _update_row_cells(self, display_symbols: list[str]) -> None:
        page = self._page
        colors = market_colors(theme_manager().tokens())
        warning_color = theme_manager().tokens().semantic_warning
        self._building = True
        for row, vt_symbol in enumerate(display_symbols):
            self._fill_row(row, vt_symbol, colors=colors, warning_color=warning_color, page=page)
        self._building = False

    def _fill_row(
        self,
        row: int,
        vt_symbol: str,
        *,
        colors,
        warning_color: str,
        page: QuotesPage,
    ) -> None:
        item = page.find_stock_item(vt_symbol)
        quote = page.quote_map.get(item.tickflow_symbol) if item is not None else None
        snapshot = page.signal_cache.get(vt_symbol)
        missing_kline = signal_missing_kline(snapshot)
        values = self._row_values(item, snapshot, quote)
        tooltip = self._row_tooltip(snapshot, values)
        for col, (key, _label) in enumerate(_PANEL_COLUMNS):
            text = values.get(key, "—")
            cell = self._table.item(row, col)
            if cell is None:
                cell = QtWidgets.QTableWidgetItem(text)
                self._table.setItem(row, col, cell)
            elif cell.text() != text:
                cell.setText(text)
            cell.setData(QtCore.Qt.ItemDataRole.UserRole, vt_symbol)
            fg = None
            if key == "signal":
                fg = signal_cell_color(key, snapshot, colors=colors)
            if missing_kline and key == "signal":
                fg = warning_color
            if fg:
                cell.setForeground(QtGui.QColor(fg))
            else:
                cell.setData(QtCore.Qt.ItemDataRole.ForegroundRole, None)
            cell.setToolTip(tooltip)

    def _row_tooltip(self, snapshot: SignalSnapshot | None, values: dict[str, str]) -> str:
        lines: list[str] = []
        if snapshot is None:
            reason = values.get("signal_reason")
            if reason and reason != "—":
                lines.append(reason)
            return "\n".join(lines)
        signal_date = values.get("signal_date") or snapshot.signal_date or "—"
        if signal_date != "—":
            lines.append(f"信号日：{signal_date}")
        dist = values.get("dist_buy_pct", "—")
        if dist != "—":
            lines.append(f"距买价%：{dist}")
        reason = values.get("signal_reason") or snapshot.reason_summary
        if reason and reason != "—":
            lines.append(f"理由：{reason}")
        if snapshot.tooltip:
            if lines:
                lines.append("")
            lines.append(snapshot.tooltip)
        return "\n".join(line for line in lines if line)

    def _row_values(self, item, snapshot: SignalSnapshot | None, quote) -> dict[str, str]:
        values: dict[str, str] = {
            "symbol": item.symbol if item is not None else "—",
            "name": (item.name if item is not None else "—") or "—",
        }
        if snapshot is None:
            for col_key, _ in _PANEL_COLUMNS:
                if col_key not in values:
                    values[col_key] = "—"
            for key in _DETAIL_COLUMN_KEYS:
                values[key] = "—"
            if item is not None:
                values["signal_reason"] = "待计算"
            return values

        for key, _ in _PANEL_COLUMNS:
            if key in {"symbol", "name"}:
                continue
            text, _ = signal_cell_text(key, snapshot, quote=quote)
            values[key] = text
        for key in _DETAIL_COLUMN_KEYS:
            text, _ = signal_cell_text(key, snapshot, quote=quote)
            values[key] = text
        if snapshot.warnings:
            values["signal_reason"] = snapshot.warnings[0]
        return values

    def _filtered_symbols(self) -> list[str]:
        if not self._signal_filter:
            return list(self._symbols)
        filtered: list[str] = []
        for vt in self._symbols:
            snap = self._page.signal_cache.get(vt)
            if self._signal_filter == "missing":
                if signal_missing_kline(snap):
                    filtered.append(vt)
            elif snap is not None and snap.signal == self._signal_filter:
                filtered.append(vt)
        return filtered

    def _stats_link(self, key: str, label: str, color: str) -> str:
        active = self._signal_filter == key
        style = f"color:{color};text-decoration:{'underline' if active else 'none'}"
        return f'<a href="{key}" style="{style}">{label}</a>'

    def _refresh_stats(self) -> None:
        colors = market_colors(theme_manager().tokens())
        warning_color = theme_manager().tokens().semantic_warning
        buy_n = sell_n = hold_n = missing_n = 0
        for vt in self._symbols:
            snap = self._page.signal_cache.get(vt)
            if snap is None:
                continue
            if signal_missing_kline(snap):
                missing_n += 1
            if snap.signal == "buy":
                buy_n += 1
            elif snap.signal == "sell":
                sell_n += 1
            elif snap.signal == "hold":
                hold_n += 1
        parts = [f"监控 {len(self._symbols)}/{SIGNAL_PANEL_MAX_SYMBOLS} 只"]
        if self._updated_at:
            parts.append(f"更新 {self._updated_at}")
        if self._signal_filter:
            filter_labels = {
                "buy": "买",
                "sell": "卖",
                "hold": "观望",
                "missing": "缺日 K",
            }
            parts.append(f"筛选 {filter_labels.get(self._signal_filter, self._signal_filter)}")
        if missing_n:
            parts.append(self._stats_link("missing", f"缺日 K {missing_n}", warning_color))
        if buy_n:
            parts.append(self._stats_link("buy", f"买 {buy_n}", colors.rise))
        if sell_n:
            parts.append(self._stats_link("sell", f"卖 {sell_n}", colors.fall))
        if hold_n:
            parts.append(self._stats_link("hold", f"观望 {hold_n}", colors.flat))
        self._stats_label.setText("  |  ".join(parts))

    def _on_stats_filter_link(self, link: str) -> None:
        key = (link or "").strip()
        if not key:
            return
        if self._signal_filter == key:
            self._signal_filter = None
        else:
            self._signal_filter = key
        self.render()

    def _on_enabled_toggled(self, enabled: bool) -> None:
        save_signal_panel_enabled(enabled)
        self._apply_enabled(enabled)
        self.enabled_changed.emit(enabled)

    def _apply_enabled(self, enabled: bool) -> None:
        for widget in (
            self._strategy_label,
            self._fast_spin,
            self._slow_spin,
            self._remove_button,
            self._clear_button,
            self._refresh_button,
            self._table,
        ):
            widget.setEnabled(enabled)

    def _on_remove_clicked(self) -> None:
        item = self._page.current_item
        fallback = item.vt_symbol if item else None
        removed = self.remove_with_fallback(fallback)
        if removed:
            self._page._toast.success(f"已移出信号区 {removed} 只")
        else:
            self._page._toast.warning("请在信号区选择要移出的标的，或在自选表选中已在名单中的标的")

    def _on_clear_clicked(self) -> None:
        if not self._symbols:
            self._page._toast.info("信号区暂无监控标的")
            return
        count = len(self._symbols)
        reply = QtWidgets.QMessageBox.question(
            self,
            "清空信号区",
            f"确定移出全部 {count} 只监控标的？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.set_symbols([], save=True)
        self.symbols_changed.emit()
        self._page._toast.success(f"已清空信号区 {count} 只")

    def _on_collapse_toggled(self, expanded: bool) -> None:
        save_signal_panel_expanded(expanded)
        self.set_expanded(expanded)

    def _sync_collapse_button(self) -> None:
        self._collapse_button.blockSignals(True)
        self._collapse_button.setChecked(self._expanded)
        self._collapse_button.setArrowType(QtCore.Qt.ArrowType.DownArrow if self._expanded else QtCore.Qt.ArrowType.RightArrow)
        self._collapse_button.blockSignals(False)

    def _apply_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        self._sync_collapse_button()
        for widget in self._body_widgets:
            widget.setVisible(expanded)
        if expanded:
            has_symbols = bool(self._symbols)
            display_symbols = self._filtered_symbols()
            self._table.setVisible(has_symbols and bool(display_symbols))
            self._empty_label.setVisible(has_symbols and not display_symbols)
            if not has_symbols:
                self._empty_label.setText(_EMPTY_LIST_TEXT)
                self._empty_label.setVisible(True)
            elif not display_symbols:
                self._empty_label.setText(_FILTER_EMPTY_TEXT)
                self._empty_label.setVisible(True)
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(120)
        else:
            self.setMinimumHeight(28)
            self.setMaximumHeight(36)
        if emit:
            self.expansion_changed.emit(expanded)

    def _emit_config_changed(self) -> None:
        if self._building:
            return
        self.config_changed.emit()

    def _on_table_selection_changed(self) -> None:
        if self._building or self._suppress_selection_signal:
            return
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        item = self._table.item(rows[0].row(), 0)
        if item is None:
            return
        vt = str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "")
        if vt:
            self.row_selected.emit(vt)

    def _on_cell_activated(self, row: int, _col: int) -> None:
        if row < 0 or row >= self._table.rowCount():
            return
        item = self._table.item(row, 0)
        if item is None:
            return
        vt = str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "")
        if vt:
            self.row_activated.emit(vt)
