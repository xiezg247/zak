"""自选页独立策略信号区域。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from strategies.registry import list_signal_strategy_metas
from strategies.signals import STRATEGY_SIGNAL_DEFAULTS
from vnpy_ashare.data.bar_health import format_meta_date
from vnpy_ashare.domain.signal_snapshot import (
    SIGNAL_STRENGTH_STRONG,
    SignalSnapshot,
    signal_is_fresh,
    signal_is_strong,
    signal_missing_kline,
    signal_row_sort_key,
)
from vnpy_ashare.services.signals import (
    build_price_field_explanations,
    build_runtime_signal_hints,
    format_strength_breakdown,
    resolve_display_anchor_prices,
    signal_cell_color,
    signal_cell_text,
)
from vnpy_ashare.ui.quotes.watchlist_signals.columns import (
    SIGNAL_PANEL_OPTIONAL_COLUMNS,
    resolve_signal_panel_columns,
)
from vnpy_ashare.ui.quotes.watchlist_signals.settings import (
    DEFAULT_CLASS,
    SIGNAL_PANEL_MAX_SYMBOLS,
    WatchlistSignalConfig,
    load_signal_panel_columns,
    load_signal_panel_enabled,
    load_signal_panel_expanded,
    load_signal_panel_symbols,
    normalize_signal_panel_symbols,
    save_signal_panel_columns,
    save_signal_panel_enabled,
    save_signal_panel_expanded,
    save_signal_panel_symbols,
)
from vnpy_ashare.ui.quotes.watchlist_signals.splitter import (
    SIGNAL_PANEL_COLLAPSED_HEIGHT,
    SIGNAL_PANEL_DEFAULT_HEIGHT,
)
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import market_colors

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

_DETAIL_COLUMN_KEYS = ("signal_date", "signal_reason")

_EMPTY_LIST_TEXT = f"暂无监控标的。请在上方自选表多选后点击「加入信号区」（最多 {SIGNAL_PANEL_MAX_SYMBOLS} 只）。"
_FILTER_EMPTY_TEXT = "当前筛选无匹配标的，再次点击统计项可取消筛选。"


class WatchlistSignalPanel(QtWidgets.QWidget):
    """自选页信号监控区：手动名单 + 双均线策略 + 独立表格。"""

    symbols_changed = QtCore.Signal()
    enabled_changed = QtCore.Signal(bool)
    config_changed = QtCore.Signal()
    refresh_requested = QtCore.Signal()
    row_activated = QtCore.Signal(str)
    row_selected = QtCore.Signal(str)
    register_position_requested = QtCore.Signal(str)
    ai_interpret_requested = QtCore.Signal(str)
    ai_scan_requested = QtCore.Signal()
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
        self._visible_column_keys: list[str] = load_signal_panel_columns()
        self._column_menu: QtWidgets.QMenu | None = None
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

        self._strategy_combo = QtWidgets.QComboBox(self)
        self._strategy_combo.setObjectName("SignalStrategyCombo")
        self._strategy_combo.setMinimumWidth(108)
        for meta in list_signal_strategy_metas():
            self._strategy_combo.addItem(meta.title, meta.class_name)
        self._strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)

        self._fast_spin = QtWidgets.QSpinBox(self)
        self._fast_spin.setRange(2, 60)
        self._fast_spin.setPrefix("快 ")
        self._fast_spin.setValue(page.signal_config.fast_window)

        self._slow_spin = QtWidgets.QSpinBox(self)
        self._slow_spin.setRange(3, 120)
        self._slow_spin.setPrefix("慢 ")
        self._slow_spin.setValue(page.signal_config.slow_window)

        self._register_position_button = QtWidgets.QPushButton("→ 登记持仓", self)
        self._register_position_button.setObjectName("SecondaryButton")
        self._register_position_button.clicked.connect(self._on_register_position_clicked)

        self._remove_button = QtWidgets.QPushButton("移出", self)
        self._remove_button.setObjectName("SecondaryButton")
        self._remove_button.clicked.connect(self._on_remove_clicked)

        self._clear_button = QtWidgets.QPushButton("清空", self)
        self._clear_button.setObjectName("SecondaryButton")
        self._clear_button.clicked.connect(self._on_clear_clicked)

        self._refresh_button = QtWidgets.QPushButton("刷新", self)
        self._refresh_button.setObjectName("SecondaryButton")
        self._refresh_button.clicked.connect(self.refresh_requested.emit)

        self._column_button = QtWidgets.QPushButton("列", self)
        self._column_button.setObjectName("SecondaryButton")
        self._column_button.setToolTip("选择信号区显示列")
        self._column_button.clicked.connect(self.show_column_menu)

        self._ai_button = QtWidgets.QPushButton("AI 解读", self)
        self._ai_button.setObjectName("SecondaryButton")
        self._ai_button.setToolTip("结合信号区快照与双均线工具做研究解读")
        self._ai_button.clicked.connect(self._on_ai_clicked)

        self._ai_scan_button = QtWidgets.QPushButton("AI 扫区", self)
        self._ai_scan_button.setObjectName("SecondaryButton")
        self._ai_scan_button.setToolTip("批量扫描信号区全部监控标的")
        self._ai_scan_button.clicked.connect(self.ai_scan_requested.emit)

        self._collapse_button = QtWidgets.QToolButton(self)
        self._collapse_button.setCheckable(True)
        self._collapse_button.setChecked(self._expanded)
        self._collapse_button.setArrowType(QtCore.Qt.ArrowType.DownArrow if self._expanded else QtCore.Qt.ArrowType.RightArrow)
        self._collapse_button.clicked.connect(self._on_collapse_toggled)

        header.addWidget(self._collapse_button)
        header.addWidget(QtWidgets.QLabel("策略信号", self))
        header.addWidget(self._toggle)
        header.addStretch()
        header.addWidget(self._strategy_combo)
        header.addWidget(self._fast_spin)
        header.addWidget(self._slow_spin)
        header.addWidget(self._register_position_button)
        header.addWidget(self._remove_button)
        header.addWidget(self._clear_button)
        header.addWidget(self._refresh_button)
        header.addWidget(self._column_button)
        header.addWidget(self._ai_button)
        header.addWidget(self._ai_scan_button)
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
        self._sync_table_columns(reset_rows=False)
        self._table.cellDoubleClicked.connect(self._on_cell_activated)
        self._table.itemSelectionChanged.connect(self._on_table_selection_changed)
        root.addWidget(self._table, stretch=1)

        self._empty_label = QtWidgets.QLabel(_EMPTY_LIST_TEXT, self)
        self._empty_label.setObjectName("BottomBarMeta")
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        root.addWidget(self._empty_label)

        self._fast_spin.valueChanged.connect(self._emit_config_changed)
        self._slow_spin.valueChanged.connect(self._emit_config_changed)

        self._body_widgets = (
            self._stats_label,
            self._table,
            self._empty_label,
            self._strategy_combo,
            self._fast_spin,
            self._slow_spin,
            self._register_position_button,
            self._remove_button,
            self._clear_button,
            self._refresh_button,
            self._column_button,
            self._ai_button,
            self._ai_scan_button,
        )
        self._apply_expanded(self._expanded, emit=False)
        self.apply_config(page.signal_config.normalized())
        self._apply_enabled(self._toggle.isChecked())
        self.render_panel()

    @property
    def symbols(self) -> list[str]:
        return list(self._symbols)

    @property
    def enabled(self) -> bool:
        return self._toggle.isChecked()

    def is_expanded(self) -> bool:
        return self._expanded

    def _panel_columns(self) -> tuple[tuple[str, str], ...]:
        return resolve_signal_panel_columns(self._visible_column_keys)

    def _info_column_index(self) -> int:
        return len(self._panel_columns())

    def _sync_table_columns(self, *, reset_rows: bool) -> None:
        columns = self._panel_columns()
        info_index = len(columns)
        self._table.setColumnCount(info_index + 1)
        self._table.setHorizontalHeaderLabels([label for _, label in columns] + [""])
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setMinimumHeight(140)
        header_view = self._table.horizontalHeader()
        header_view.setStretchLastSection(False)
        header_view.setSectionResizeMode(info_index, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(info_index, 52)
        for col in range(info_index):
            header_view.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        if reset_rows:
            self._rendered_symbols = []
            self._table.setRowCount(0)

    def show_column_menu(self) -> None:
        menu = self._column_menu
        if menu is None:
            menu = QtWidgets.QMenu(self)
            self._column_menu = menu
            for key, label in SIGNAL_PANEL_OPTIONAL_COLUMNS:
                action = menu.addAction(label)
                action.setCheckable(True)
                action.setData(key)
                action.triggered.connect(self._on_column_toggled)
        visible = set(self._visible_column_keys)
        for action in menu.actions():
            key = str(action.data() or "")
            action.blockSignals(True)
            action.setChecked(key in visible)
            action.blockSignals(False)
        menu.exec(self._column_button.mapToGlobal(self._column_button.rect().bottomLeft()))

    def _on_column_toggled(self, checked: bool) -> None:
        action = self.sender()
        if not isinstance(action, QtGui.QAction):
            return
        key = str(action.data() or "").strip()
        if not key:
            return
        keys = list(self._visible_column_keys)
        if checked and key not in keys:
            keys.append(key)
        elif not checked and key in keys:
            keys.remove(key)
        from vnpy_ashare.ui.quotes.watchlist_signals.columns import normalize_visible_optional_keys

        self._visible_column_keys = normalize_visible_optional_keys(keys)
        save_signal_panel_columns(self._visible_column_keys)
        self._sync_table_columns(reset_rows=True)
        self.render_panel()

    def set_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        changed = self._expanded != expanded
        self._expanded = expanded
        self._apply_expanded(expanded, emit=emit and changed)

    def sync_splitter_geometry(self) -> None:
        """供 splitter 布局前同步 min/max，避免 QSplitter 忽略目标高度。"""
        self._apply_expanded(self._expanded, emit=False)

    def read_config(self) -> WatchlistSignalConfig:
        fast = int(self._fast_spin.value())
        slow = int(self._slow_spin.value())
        if slow <= fast:
            slow = fast + 1
            self._slow_spin.blockSignals(True)
            self._slow_spin.setValue(slow)
            self._slow_spin.blockSignals(False)
        class_name = str(self._strategy_combo.currentData() or DEFAULT_CLASS)
        return WatchlistSignalConfig(
            class_name=class_name,
            fast_window=fast,
            slow_window=slow,
        ).normalized()

    def apply_config(self, config: WatchlistSignalConfig) -> None:
        item = config.normalized()
        self._strategy_combo.blockSignals(True)
        self._fast_spin.blockSignals(True)
        self._slow_spin.blockSignals(True)
        index = self._strategy_combo.findData(item.class_name)
        if index >= 0:
            self._strategy_combo.setCurrentIndex(index)
        self._fast_spin.setValue(item.fast_window)
        self._slow_spin.setValue(item.slow_window)
        self._strategy_combo.blockSignals(False)
        self._fast_spin.blockSignals(False)
        self._slow_spin.blockSignals(False)

    def _on_strategy_changed(self, _index: int) -> None:
        class_name = str(self._strategy_combo.currentData() or DEFAULT_CLASS)
        defaults = STRATEGY_SIGNAL_DEFAULTS.get(class_name)
        if defaults is not None:
            fast, slow = defaults
            self._fast_spin.blockSignals(True)
            self._slow_spin.blockSignals(True)
            self._fast_spin.setValue(fast)
            self._slow_spin.setValue(max(slow, fast + 1))
            self._fast_spin.blockSignals(False)
            self._slow_spin.blockSignals(False)
        self._emit_config_changed()

    def set_symbols(self, symbols: list[str], *, save: bool = True) -> None:
        self._symbols = normalize_signal_panel_symbols(symbols)
        if save:
            save_signal_panel_symbols(self._symbols)
        if not self._symbols:
            self._signal_filter = None
        self.render_panel()

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
            self.render_panel()
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
            self.render_panel()
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

    def render_panel(self) -> None:
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

    def update_rows_for_tickflow_symbols(self, tickflow_symbols: set[str]) -> None:
        """行情推送时仅刷新受影响行（不重建表格、不重排）。"""
        if not self._symbols or not tickflow_symbols or not self._expanded or not self.enabled:
            return
        if not self._table.isVisible():
            return

        page = self._page
        display_symbols = self._sorted_display_symbols()
        if not display_symbols:
            return

        colors = market_colors(theme_manager().tokens())
        warning_color = theme_manager().tokens().semantic_warning
        self._building = True
        try:
            for row, vt_symbol in enumerate(display_symbols):
                item = page.find_stock_item(vt_symbol)
                if item is None or item.tickflow_symbol not in tickflow_symbols:
                    continue
                self._fill_row(row, vt_symbol, colors=colors, warning_color=warning_color, page=page)
        finally:
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
        bar_end_date = self._bar_end_date(vt_symbol)
        values = self._row_values(item, snapshot, quote, bar_end_date=bar_end_date)
        tooltip = self._row_tooltip(snapshot, values, quote=quote, vt_symbol=vt_symbol)
        strength_tooltip = format_strength_breakdown(snapshot)
        for col, (key, _label) in enumerate(self._panel_columns()):
            text = values.get(key, "—")
            cell = self._table.item(row, col)
            if cell is None:
                cell = QtWidgets.QTableWidgetItem(text)
                self._table.setItem(row, col, cell)
            elif cell.text() != text:
                cell.setText(text)
            cell.setData(QtCore.Qt.ItemDataRole.UserRole, vt_symbol)
            config = page.signal_config.normalized()
            fg = signal_cell_color(
                key,
                snapshot,
                colors=colors,
                quote=quote,
                bar_end_date=bar_end_date,
                slow_window=config.slow_window,
                fast_window=config.fast_window,
                warning_color=warning_color,
            )
            if missing_kline and key == "signal":
                fg = warning_color
            if fg:
                cell.setForeground(QtGui.QColor(fg))
            else:
                cell.setData(QtCore.Qt.ItemDataRole.ForegroundRole, None)
            if key == "signal_strength" and strength_tooltip:
                cell.setToolTip(strength_tooltip)
            else:
                cell.setToolTip(tooltip)
        self._fill_info_button(row, vt_symbol)

    def _bar_end_date(self, vt_symbol: str) -> str | None:
        item = self._page.find_stock_item(vt_symbol)
        if item is None:
            return None
        meta = self._page.bar_meta.get((item.symbol, item.exchange))
        if meta is None or meta.end is None:
            return None
        return format_meta_date(meta.end)

    def _position_tooltip_lines(self, vt_symbol: str, snapshot: SignalSnapshot | None) -> list[str]:
        pos = self._page.position_cache.get(vt_symbol)
        if pos is None:
            return []
        lines = [
            f"持仓：成本 {pos.cost_price:.2f} × {pos.volume} 股，买入日 {pos.buy_date[:10]}",
        ]
        if pos.unrealized_pnl is not None and pos.unrealized_pnl_pct is not None:
            lines.append(f"浮盈：{pos.unrealized_pnl:+.2f} 元（{pos.unrealized_pnl_pct:+.2f}%）")
        if snapshot is not None and pos.unrealized_pnl_pct is not None and pos.unrealized_pnl_pct < 0:
            if snapshot.signal == "buy":
                lines.append("提示：信号买入但持仓浮亏，注意成本与结构位")
            elif snapshot.signal == "sell" and not pos.t1_locked:
                lines.append("提示：策略卖出且可卖，关注退出信号")
        return lines

    def _fill_info_button(self, row: int, vt_symbol: str) -> None:
        widget = self._table.cellWidget(row, self._info_column_index())
        if isinstance(widget, QtWidgets.QToolButton):
            btn = widget
        elif widget is None:
            btn = QtWidgets.QToolButton(self._table)
            btn.setText("理由")
            btn.setToolTip("查看信号理由")
            btn.setAutoRaise(True)
            btn.setObjectName("SignalInfoButton")
            btn.clicked.connect(self._on_info_clicked)
            self._table.setCellWidget(row, self._info_column_index(), btn)
        else:
            return
        btn.setText("理由")
        btn.setProperty("vt_symbol", vt_symbol)
        btn.setEnabled(bool(vt_symbol))

    def _on_info_clicked(self) -> None:
        sender = self.sender()
        if not isinstance(sender, QtWidgets.QToolButton):
            return
        vt_symbol = str(sender.property("vt_symbol") or "").strip()
        if not vt_symbol:
            return
        self._show_signal_reason_dialog(vt_symbol)

    def _show_signal_reason_dialog(self, vt_symbol: str) -> None:
        page = self._page
        item = page.find_stock_item(vt_symbol)
        quote = page.quote_map.get(item.tickflow_symbol) if item is not None else None
        snapshot = page.signal_cache.get(vt_symbol)
        values = self._row_values(item, snapshot, quote, bar_end_date=self._bar_end_date(vt_symbol))
        title_name = values.get("name") or vt_symbol
        detail = self._row_tooltip(snapshot, values, quote=quote, vt_symbol=vt_symbol)
        if not detail.strip():
            detail = "暂无信号理由。"

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"策略信号 · {title_name}")
        dialog.setMinimumSize(520, 360)
        dialog.resize(640, 480)
        layout = QtWidgets.QVBoxLayout(dialog)
        editor = QtWidgets.QPlainTextEdit(dialog)
        editor.setReadOnly(True)
        editor.setPlainText(detail)
        editor.setMinimumHeight(320)
        editor.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(editor, stretch=1)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        close_btn = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def _row_tooltip(
        self,
        snapshot: SignalSnapshot | None,
        values: dict[str, str],
        *,
        quote,
        vt_symbol: str = "",
    ) -> str:
        lines: list[str] = []
        if snapshot is None:
            reason = values.get("signal_reason")
            if reason and reason != "—":
                lines.append(reason)
            lines.extend(self._position_tooltip_lines(vt_symbol, None))
            return "\n".join(lines)
        signal_date = values.get("signal_date") or snapshot.signal_date or "—"
        if signal_date != "—":
            lines.append(f"信号日：{signal_date}")
        if snapshot.as_of:
            lines.append(f"K 线截止：{snapshot.as_of}")
        config = self._page.signal_config.normalized()
        lines.append("【字段说明】")
        lines.extend(
            build_price_field_explanations(
                snapshot.signal,
                fast_window=config.fast_window,
                slow_window=config.slow_window,
            )
        )
        lines.append("")
        lines.append("【当前数值】")
        display_buy, display_sell, adjusted = resolve_display_anchor_prices(
            snapshot,
            quote=quote,
            slow_window=config.slow_window,
            fast_window=config.fast_window,
        )
        if snapshot.ref_buy_price is not None:
            lines.append(f"支撑锚点（结构）：{snapshot.ref_buy_price:.2f}")
        if snapshot.ref_sell_price is not None:
            lines.append(f"阻力锚点（结构）：{snapshot.ref_sell_price:.2f}")
        if adjusted:
            if display_buy is not None:
                lines.append(f"支撑锚点（盘中估算）：{display_buy:.2f}")
            if display_sell is not None:
                lines.append(f"阻力锚点（盘中估算）：{display_sell:.2f}")
        ref_buy = values.get("ref_buy_price", "—")
        ref_sell = values.get("ref_sell_price", "—")
        if ref_buy != "—":
            lines.append(f"参考买价：{ref_buy}")
        if ref_sell != "—":
            lines.append(f"参考卖价：{ref_sell}")
        dist = values.get("dist_buy_pct", "—")
        if dist != "—":
            lines.append(f"距买价%：{dist}")
        dist_sell = values.get("dist_sell_pct", "—")
        if dist_sell != "—":
            lines.append(f"距卖价%：{dist_sell}")
        runtime_hints = build_runtime_signal_hints(
            snapshot,
            quote=quote,
            slow_window=config.slow_window,
            fast_window=config.fast_window,
        )
        if runtime_hints:
            lines.extend(runtime_hints)
        lines.extend(self._position_tooltip_lines(snapshot.vt_symbol, snapshot))
        breakdown = format_strength_breakdown(snapshot)
        if breakdown:
            lines.append("")
            lines.append("【强度分解】")
            lines.append(breakdown)
        if snapshot is not None:
            reason = values.get("signal_reason") or snapshot.reason_summary
            if reason and reason != "—":
                lines.append(f"理由：{reason}")
            if snapshot.tooltip:
                if lines:
                    lines.append("")
                lines.append(snapshot.tooltip)
        return "\n".join(line for line in lines if line)

    def _row_values(
        self,
        item,
        snapshot: SignalSnapshot | None,
        quote,
        *,
        bar_end_date: str | None = None,
    ) -> dict[str, str]:
        values: dict[str, str] = {
            "symbol": item.symbol if item is not None else "—",
            "name": (item.name if item is not None else "—") or "—",
        }
        if snapshot is None:
            for col_key, _ in self._panel_columns():
                if col_key not in values:
                    values[col_key] = "—"
            for key in _DETAIL_COLUMN_KEYS:
                values[key] = "—"
            if item is not None:
                values["signal_reason"] = "待计算"
            return values

        config = self._page.signal_config.normalized()
        cell_kwargs = {
            "quote": quote,
            "bar_end_date": bar_end_date,
            "slow_window": config.slow_window,
            "fast_window": config.fast_window,
        }
        for key, _ in self._panel_columns():
            if key in {"symbol", "name"}:
                continue
            text, _ = signal_cell_text(key, snapshot, **cell_kwargs)
            values[key] = text
        for key in _DETAIL_COLUMN_KEYS:
            text, _ = signal_cell_text(key, snapshot, **cell_kwargs)
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
            elif self._signal_filter == "fresh":
                if snap is not None and signal_is_fresh(snap):
                    filtered.append(vt)
            elif self._signal_filter == "strong":
                if snap is not None and signal_is_strong(snap):
                    filtered.append(vt)
            elif self._signal_filter == "held":
                if vt in self._page.position_cache:
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
        buy_n = sell_n = hold_n = missing_n = fresh_n = strong_n = held_n = 0
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
            if signal_is_fresh(snap):
                fresh_n += 1
            if signal_is_strong(snap):
                strong_n += 1
            if vt in self._page.position_cache:
                held_n += 1
        parts = [f"监控 {len(self._symbols)}/{SIGNAL_PANEL_MAX_SYMBOLS} 只"]
        if self._updated_at:
            parts.append(f"更新 {self._updated_at}")
        if self._signal_filter:
            filter_labels = {
                "buy": "买",
                "sell": "卖",
                "hold": "观望",
                "missing": "缺日 K",
                "fresh": "新信号",
                "strong": f"强≥{int(SIGNAL_STRENGTH_STRONG)}",
                "held": "已持仓",
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
        if fresh_n:
            parts.append(self._stats_link("fresh", f"新信号 {fresh_n}", colors.rise))
        if strong_n:
            parts.append(self._stats_link("strong", f"强≥{int(SIGNAL_STRENGTH_STRONG)} {strong_n}", colors.rise))
        if held_n:
            parts.append(self._stats_link("held", f"已持仓 {held_n}", colors.flat))
        self._stats_label.setText("  |  ".join(parts))

    def _on_stats_filter_link(self, link: str) -> None:
        key = (link or "").strip()
        if not key:
            return
        if self._signal_filter == key:
            self._signal_filter = None
        else:
            self._signal_filter = key
        self.render_panel()

    def _on_enabled_toggled(self, enabled: bool) -> None:
        save_signal_panel_enabled(enabled)
        self._apply_enabled(enabled)
        self.enabled_changed.emit(enabled)

    def _apply_enabled(self, enabled: bool) -> None:
        for widget in (
            self._strategy_combo,
            self._fast_spin,
            self._slow_spin,
            self._register_position_button,
            self._remove_button,
            self._clear_button,
            self._refresh_button,
            self._column_button,
            self._ai_button,
            self._ai_scan_button,
            self._table,
        ):
            widget.setEnabled(enabled)

    def _on_ai_clicked(self) -> None:
        symbols = self.selected_vt_symbols()
        if len(symbols) == 1:
            self.ai_interpret_requested.emit(symbols[0])
            return
        if len(symbols) > 1:
            self._page._toast.warning("AI 解读一次仅支持单只标的")
            return
        item = self._page.current_item
        if item is not None and item.vt_symbol in self._symbols:
            self.ai_interpret_requested.emit(item.vt_symbol)
            return
        self._page._toast.warning("请先在策略信号区选择标的")

    def _on_register_position_clicked(self) -> None:
        symbols = self.selected_vt_symbols()
        if not symbols:
            self._page._toast.warning("请先在策略信号区选择标的")
            return
        if len(symbols) > 1:
            self._page._toast.warning("登记持仓一次仅支持单只标的")
            return
        self.register_position_requested.emit(symbols[0])

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
            self.setMinimumHeight(SIGNAL_PANEL_DEFAULT_HEIGHT)
        else:
            self.setMinimumHeight(SIGNAL_PANEL_COLLAPSED_HEIGHT)
            self.setMaximumHeight(SIGNAL_PANEL_COLLAPSED_HEIGHT + 4)
        if emit:
            self.expansion_changed.emit(expanded)

    def _emit_config_changed(self) -> None:
        if self._building:
            self._page.apply_signal_panel_config()
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
