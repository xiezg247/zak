"""自选页持仓策略区域。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.position_snapshot import PositionRecord, position_row_sort_key, position_t1_locked
from vnpy_ashare.domain.signal_snapshot import signal_cell_color, signal_missing_kline
from vnpy_ashare.storage.app_db import POSITION_MAX_ITEMS
from vnpy_ashare.ui.quotes.watchlist_positions.dialog import PositionEditDialog
from vnpy_ashare.ui.quotes.watchlist_positions.settings import (
    POSITION_PANEL_COLLAPSED_HEIGHT,
    POSITION_PANEL_DEFAULT_HEIGHT,
    WatchlistPositionConfig,
    load_position_panel_enabled,
    load_position_panel_expanded,
    save_position_panel_enabled,
    save_position_panel_expanded,
)
from vnpy_ashare.ui.quotes.watchlist_signals.settings import WatchlistSignalConfig
from strategies.registry import get_strategy_meta
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import market_colors

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

_PANEL_COLUMNS = (
    ("symbol", "代码"),
    ("name", "名称"),
    ("cost_price", "成本价"),
    ("volume", "持仓量(股)"),
    ("buy_date", "买入日"),
    ("last_price", "现价"),
    ("pnl", "浮盈(元)"),
    ("pnl_pct", "浮盈%"),
    ("t1_status", "T+1"),
    ("exit_signal", "退出信号"),
    ("ref_sell_price", "参考卖价"),
)

_EMPTY_TEXT = f"暂无持仓。请在上方自选表选中标的后点击「登记持仓」（最多 {POSITION_MAX_ITEMS} 只）。"
_FILTER_EMPTY_TEXT = "当前筛选无匹配标的，再次点击统计项可取消筛选。"


class WatchlistPositionPanel(QtWidgets.QWidget):
    rows_changed = QtCore.Signal()
    enabled_changed = QtCore.Signal(bool)
    config_changed = QtCore.Signal()
    refresh_requested = QtCore.Signal()
    row_activated = QtCore.Signal(str)
    row_selected = QtCore.Signal(str)
    expansion_changed = QtCore.Signal(bool)

    def __init__(self, page: QuotesPage) -> None:
        super().__init__(page)
        self._page = page
        self._updated_at = ""
        self._building = False
        self._expanded = load_position_panel_expanded()
        self._filter: str | None = None
        self._rendered_symbols: list[str] = []
        self._suppress_selection_signal = False

        self.setObjectName("WatchlistPositionPanel")
        theme_manager().bind_stylesheet(self)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)

        self._toggle = QtWidgets.QCheckBox("启用持仓", self)
        self._toggle.setChecked(load_position_panel_enabled())
        self._toggle.toggled.connect(self._on_enabled_toggled)

        position_cfg = page.position_config.normalized()
        self._follow_check = QtWidgets.QCheckBox("跟随信号区", self)
        self._follow_check.setChecked(position_cfg.follow_signal)
        self._follow_check.toggled.connect(self._on_follow_toggled)

        self._strategy_label = QtWidgets.QLabel("", self)
        self._strategy_label.setObjectName("SectionLabel")

        self._fast_spin = QtWidgets.QSpinBox(self)
        self._fast_spin.setRange(2, 60)
        self._fast_spin.setPrefix("快 ")
        self._fast_spin.setValue(position_cfg.fast_window)

        self._slow_spin = QtWidgets.QSpinBox(self)
        self._slow_spin.setRange(3, 120)
        self._slow_spin.setPrefix("慢 ")
        self._slow_spin.setValue(position_cfg.slow_window)

        self._edit_button = QtWidgets.QPushButton("编辑", self)
        self._edit_button.setObjectName("SecondaryButton")
        self._edit_button.clicked.connect(self._on_edit_clicked)

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
        header.addWidget(QtWidgets.QLabel("持仓策略", self))
        header.addWidget(self._toggle)
        header.addStretch()
        header.addWidget(self._follow_check)
        header.addWidget(self._strategy_label)
        header.addWidget(self._fast_spin)
        header.addWidget(self._slow_spin)
        header.addWidget(self._edit_button)
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
        self._table.setObjectName("WatchlistPositionTable")
        self._table.setColumnCount(len(_PANEL_COLUMNS))
        self._table.setHorizontalHeaderLabels([label for _, label in _PANEL_COLUMNS])
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        root.addWidget(self._table, stretch=1)

        self._fast_spin.valueChanged.connect(self._emit_config_changed)
        self._slow_spin.valueChanged.connect(self._emit_config_changed)
        self._sync_strategy_controls(signal_config=page.signal_config)
        self._sync_expansion_ui()
        self.render()

    @property
    def enabled(self) -> bool:
        return self._toggle.isChecked()

    def is_expanded(self) -> bool:
        return self._expanded

    def minimumHeight(self) -> int:
        return POSITION_PANEL_DEFAULT_HEIGHT if self._expanded else POSITION_PANEL_COLLAPSED_HEIGHT

    def set_updated_at(self, text: str) -> None:
        self._updated_at = text

    def read_config(self) -> WatchlistPositionConfig:
        fast = int(self._fast_spin.value())
        slow = int(self._slow_spin.value())
        if slow <= fast:
            slow = fast + 1
            self._slow_spin.blockSignals(True)
            self._slow_spin.setValue(slow)
            self._slow_spin.blockSignals(False)
        return WatchlistPositionConfig(
            follow_signal=self._follow_check.isChecked(),
            class_name=self._page.position_config.class_name,
            fast_window=fast,
            slow_window=slow,
        ).normalized()

    def apply_config(self, config: WatchlistPositionConfig) -> None:
        item = config.normalized()
        self._follow_check.blockSignals(True)
        self._fast_spin.blockSignals(True)
        self._slow_spin.blockSignals(True)
        self._follow_check.setChecked(item.follow_signal)
        self._fast_spin.setValue(item.fast_window)
        self._slow_spin.setValue(item.slow_window)
        self._follow_check.blockSignals(False)
        self._fast_spin.blockSignals(False)
        self._slow_spin.blockSignals(False)
        self._sync_strategy_controls(
            signal_config=self._page.signal_config if item.follow_signal else None,
        )

    def set_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded
        save_position_panel_expanded(expanded)
        self._sync_expansion_ui()
        if emit:
            self.expansion_changed.emit(expanded)

    def highlight_symbol(self, vt_symbol: str) -> None:
        if not vt_symbol:
            return
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is not None and item.data(QtCore.Qt.ItemDataRole.UserRole) == vt_symbol:
                self._suppress_selection_signal = True
                self._table.selectRow(row)
                self._suppress_selection_signal = False
                return

    def _records(self) -> list[PositionRecord]:
        service = self._page._get_position_service()
        if service is None:
            return []
        return service.get_items()

    def _filtered_records(self) -> list[PositionRecord]:
        records = self._records()
        if not self._filter:
            return records
        filtered: list[PositionRecord] = []
        for record in records:
            snap = self._page.position_cache.get(record.vt_symbol)
            if self._filter == "missing":
                if snap is None or signal_missing_kline(snap.signal_snapshot):
                    filtered.append(record)
            elif self._filter == "t1":
                if snap is not None and snap.t1_locked:
                    filtered.append(record)
            elif snap is not None and snap.exit_signal == self._filter:
                filtered.append(record)
        return filtered

    def _sync_expansion_ui(self) -> None:
        expanded = self._expanded
        self._collapse_button.setChecked(expanded)
        self._collapse_button.setArrowType(QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow)
        self._table.setVisible(expanded)
        self._stats_label.setVisible(expanded)
        for widget in (
            self._toggle,
            self._follow_check,
            self._strategy_label,
            self._fast_spin,
            self._slow_spin,
            self._edit_button,
            self._remove_button,
            self._clear_button,
            self._refresh_button,
        ):
            widget.setVisible(expanded)
        self.setMinimumHeight(self.minimumHeight())
        self.setMaximumHeight(16777215 if expanded else POSITION_PANEL_COLLAPSED_HEIGHT)

    def _strategy_title(self, class_name: str) -> str:
        meta = get_strategy_meta(class_name)
        return meta.title if meta is not None else class_name

    def _sync_strategy_controls(self, signal_config: WatchlistSignalConfig | None = None) -> None:
        follow = self._follow_check.isChecked()
        if follow:
            cfg = (signal_config or self._page.signal_config).normalized()
            self._strategy_label.setText(f"跟随·{self._strategy_title(cfg.class_name)}")
            self._strategy_label.setVisible(True)
            self._fast_spin.setVisible(False)
            self._slow_spin.setVisible(False)
            return
        item = self._page.position_config.normalized()
        self._strategy_label.setText(self._strategy_title(item.class_name))
        self._strategy_label.setVisible(True)
        self._fast_spin.setVisible(True)
        self._slow_spin.setVisible(True)
        self._fast_spin.setEnabled(True)
        self._slow_spin.setEnabled(True)

    def sync_follow_display(self, signal_config: WatchlistSignalConfig) -> None:
        """跟随信号区时，同步展示当前策略名称。"""
        if not self._follow_check.isChecked():
            return
        self._sync_strategy_controls(signal_config=signal_config)

    def _on_follow_toggled(self, _checked: bool) -> None:
        self._sync_strategy_controls(signal_config=self._page.signal_config)
        self._emit_config_changed()

    def _emit_config_changed(self) -> None:
        if self._building:
            return
        self.config_changed.emit()

    def _on_enabled_toggled(self, checked: bool) -> None:
        save_position_panel_enabled(checked)
        self.enabled_changed.emit(checked)

    def _on_collapse_toggled(self, checked: bool) -> None:
        self.set_expanded(checked)

    def _on_selection_changed(self) -> None:
        if self._suppress_selection_signal:
            return
        vt_symbol = self._selected_vt_symbol()
        if vt_symbol:
            self.row_selected.emit(vt_symbol)

    def _on_cell_double_clicked(self, row: int, _col: int) -> None:
        item = self._table.item(row, 0)
        if item is None:
            return
        vt_symbol = str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "")
        if vt_symbol:
            self.row_activated.emit(vt_symbol)
            self._on_edit_clicked()

    def _selected_vt_symbol(self) -> str:
        row = self._table.currentRow()
        if row < 0:
            return ""
        item = self._table.item(row, 0)
        if item is None:
            return ""
        return str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "").strip()

    def _on_edit_clicked(self) -> None:
        vt_symbol = self._selected_vt_symbol()
        if not vt_symbol:
            main_item = self._page.current_item
            if main_item is not None:
                vt_symbol = main_item.vt_symbol
        if not vt_symbol:
            self._page._toast.warning("请先选择要编辑的持仓")
            return
        record = next((row for row in self._records() if row.vt_symbol == vt_symbol), None)
        if record is None:
            self._page._toast.warning("该标的尚未登记持仓")
            return
        item = self._page.find_stock_item(vt_symbol)
        title = f"编辑持仓 · {item.symbol if item else vt_symbol}"
        dialog = PositionEditDialog(title=title, symbol_text=vt_symbol, record=record, parent=self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self._save_form(vt_symbol, dialog.read_form(), existing=True)

    def _save_form(self, vt_symbol: str, form, *, existing: bool) -> None:
        service = self._page._get_position_service()
        if service is None:
            self._page.status_label.setText("持仓服务未就绪")
            return
        item = self._page.find_stock_item(vt_symbol)
        if item is None:
            self._page._toast.warning("标的不在自选池")
            return
        error = service.validate_inputs(cost_price=form.cost_price, volume=form.volume, buy_date=form.buy_date)
        if error:
            self._page._toast.warning(error)
            return
        if existing:
            ok = service.update(
                item.symbol,
                item.exchange,
                cost_price=form.cost_price,
                volume=form.volume,
                buy_date=form.buy_date,
                notes=form.notes,
            )
        else:
            ok = service.add(
                item.symbol,
                item.exchange,
                cost_price=form.cost_price,
                volume=form.volume,
                buy_date=form.buy_date,
                notes=form.notes,
            )
        if not ok:
            reason = service.add_failure_reason(item.symbol, item.exchange) if not existing else None
            if reason == "full":
                self._page._toast.warning(f"持仓已满（最多 {POSITION_MAX_ITEMS} 只）")
            elif reason == "duplicate":
                self._page._toast.warning("该标的已登记持仓")
            elif reason == "not_in_watchlist":
                self._page._toast.warning("须先将标的加入自选池")
            else:
                self._page._toast.warning("保存失败")
            return
        self._page.status_label.setText(f"已保存持仓：{vt_symbol}")
        self.rows_changed.emit()

    def register_symbol(self, vt_symbol: str) -> bool:
        service = self._page._get_position_service()
        if service is None:
            self._page.status_label.setText("持仓服务未就绪")
            return False
        item = self._page.find_stock_item(vt_symbol)
        if item is None:
            return False
        if service.contains(item.symbol, item.exchange):
            self._page._toast.warning("该标的已登记持仓，请使用编辑")
            return False
        title = f"登记持仓 · {item.symbol}"
        dialog = PositionEditDialog(title=title, symbol_text=vt_symbol, parent=self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return False
        self._save_form(vt_symbol, dialog.read_form(), existing=False)
        return True

    def _on_remove_clicked(self) -> None:
        vt_symbol = self._selected_vt_symbol()
        if not vt_symbol:
            item = self._page.current_item
            if item is not None:
                vt_symbol = item.vt_symbol
        if not vt_symbol:
            self._page._toast.warning("请先选择要移出的持仓")
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "移出持仓",
            f"确认移出 {vt_symbol} 的持仓记录？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        stock = self._page.find_stock_item(vt_symbol)
        service = self._page._get_position_service()
        if stock is None or service is None:
            return
        if service.remove(stock.symbol, stock.exchange):
            self._page.position_cache.pop(vt_symbol, None)
            self._page.status_label.setText(f"已移出持仓：{vt_symbol}")
            self.rows_changed.emit()

    def _on_clear_clicked(self) -> None:
        if not self._records():
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "清空持仓",
            "确认清空全部持仓记录？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        service = self._page._get_position_service()
        if service is None:
            return
        service.clear()
        self._page._positions.invalidate_cache()
        self._page.status_label.setText("已清空全部持仓")
        self.rows_changed.emit()

    def _on_stats_filter_link(self, href: str) -> None:
        key = href.strip()
        if self._filter == key:
            self._filter = None
        else:
            self._filter = key
        self.render()

    def _stats_link(self, key: str, label: str, color: str) -> str:
        active = self._filter == key
        style = f"color:{color};text-decoration:{'underline' if active else 'none'}"
        return f'<a href="{key}" style="{style}">{label}</a>'

    def _refresh_stats(self) -> None:
        colors = market_colors(theme_manager().tokens())
        warning_color = theme_manager().tokens().semantic_warning
        records = self._records()
        sell_count = t1_count = missing_count = 0
        total_pnl = 0.0
        has_pnl = False
        for record in records:
            snap = self._page.position_cache.get(record.vt_symbol)
            if snap is None:
                missing_count += 1
                continue
            if signal_missing_kline(snap.signal_snapshot):
                missing_count += 1
            if snap.exit_signal == "sell":
                sell_count += 1
            if snap.t1_locked:
                t1_count += 1
            if snap.unrealized_pnl is not None:
                total_pnl += snap.unrealized_pnl
                has_pnl = True
        pnl_text = f"{total_pnl:+.2f}" if has_pnl else "—"
        updated = f" · 更新 {self._updated_at}" if self._updated_at else ""
        parts = [
            f"持仓 {len(records)}",
            f"总浮盈 {pnl_text}",
            self._stats_link("sell", f"卖出信号 {sell_count}", colors.fall),
            self._stats_link("t1", f"T+1 {t1_count}", colors.flat),
            self._stats_link("missing", f"缺日K {missing_count}", warning_color),
        ]
        self._stats_label.setText(" · ".join(parts) + updated)

    def _row_values(self, record: PositionRecord):
        snap = self._page.position_cache.get(record.vt_symbol)
        item = self._page.find_stock_item(record.vt_symbol)
        quote = self._page.quote_map.get(item.tickflow_symbol) if item is not None else None
        last_price = None
        if snap is not None and snap.last_price is not None:
            last_price = snap.last_price
        elif quote is not None and quote.last_price > 0:
            last_price = quote.last_price
        buy_date = (record.buy_date or "")[:10] or "—"
        values = {
            "symbol": record.symbol,
            "name": record.name or (item.name if item else "—"),
            "cost_price": f"{record.cost_price:.2f}",
            "volume": str(record.volume),
            "buy_date": buy_date,
            "last_price": f"{last_price:.2f}" if last_price is not None else "—",
        }
        locked = position_t1_locked(buy_date) if buy_date != "—" else False
        values["t1_status"] = "T+1 锁定" if locked else "可卖"
        if snap is None:
            values["pnl"] = "—"
            values["pnl_pct"] = "—"
            values["exit_signal"] = "待计算"
            values["ref_sell_price"] = "—"
            return values, snap, quote
        pnl = snap.unrealized_pnl
        values["pnl"] = f"{pnl:+.2f}" if pnl is not None else "—"
        pnl_pct = snap.unrealized_pnl_pct
        values["pnl_pct"] = f"{pnl_pct:+.2f}%" if pnl_pct is not None else "—"
        values["t1_status"] = snap.t1_status_label
        values["exit_signal"] = snap.exit_signal_label
        ref_sell = snap.exit_ref_price
        values["ref_sell_price"] = f"{ref_sell:.2f}" if ref_sell is not None else "—"
        return values, snap, quote

    def render(self) -> None:
        if self._building:
            return
        self._building = True
        try:
            records = self._filtered_records()
            records = sorted(
                records,
                key=lambda record: position_row_sort_key(
                    self._page.position_cache[record.vt_symbol]
                )
                if record.vt_symbol in self._page.position_cache
                else (9, 0.0, record.vt_symbol),
            )
            colors = market_colors(theme_manager().tokens())
            warning_color = theme_manager().tokens().semantic_warning

            if not self._records():
                self._table.setRowCount(1)
                cell = QtWidgets.QTableWidgetItem(_EMPTY_TEXT)
                cell.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                self._table.setItem(0, 0, cell)
                self._table.setSpan(0, 0, 1, len(_PANEL_COLUMNS))
                self._stats_label.setText("")
                self._rendered_symbols = []
                return

            if not records:
                self._table.setRowCount(1)
                cell = QtWidgets.QTableWidgetItem(_FILTER_EMPTY_TEXT)
                cell.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                self._table.setItem(0, 0, cell)
                self._table.setSpan(0, 0, 1, len(_PANEL_COLUMNS))
                self._refresh_stats()
                self._rendered_symbols = []
                return

            self._table.clearSpans()
            if len(records) != self._table.rowCount():
                self._table.setRowCount(len(records))

            rendered: list[str] = []
            for row, record in enumerate(records):
                rendered.append(record.vt_symbol)
                values, snap, quote = self._row_values(record)
                buy_date = values.get("buy_date", "—")
                t1_locked = (
                    snap.t1_locked
                    if snap is not None
                    else (position_t1_locked(buy_date) if buy_date != "—" else False)
                )
                config = self._page.position_config.normalized().effective_signal_config(
                    self._page.signal_config
                )
                for col, (key, _label) in enumerate(_PANEL_COLUMNS):
                    text = values.get(key, "—")
                    cell = self._table.item(row, col)
                    if cell is None:
                        cell = QtWidgets.QTableWidgetItem(text)
                        self._table.setItem(row, col, cell)
                    elif cell.text() != text:
                        cell.setText(text)
                    cell.setData(QtCore.Qt.ItemDataRole.UserRole, record.vt_symbol)
                    fg = None
                    if key == "pnl" and snap is not None and snap.unrealized_pnl is not None:
                        fg = colors.rise if snap.unrealized_pnl >= 0 else colors.fall
                    elif key == "pnl_pct" and snap is not None and snap.unrealized_pnl_pct is not None:
                        fg = colors.rise if snap.unrealized_pnl_pct >= 0 else colors.fall
                    elif key == "t1_status":
                        if t1_locked:
                            fg = warning_color
                        elif snap is not None:
                            fg = colors.flat
                    elif key == "exit_signal" and snap is not None and snap.signal_snapshot is not None:
                        fg = signal_cell_color(
                            "signal",
                            snap.signal_snapshot,
                            colors=colors,
                            quote=quote,
                            warning_color=warning_color,
                            slow_window=config.slow_window,
                            fast_window=config.fast_window,
                        )
                    if key == "t1_status":
                        if snap is not None:
                            cell.setToolTip(snap.t1_status_tooltip)
                        elif buy_date != "—":
                            tip = (
                                f"买入日 {buy_date}：当日买入不可卖（A 股 T+1）"
                                if t1_locked
                                else f"买入日 {buy_date}：已过 T+1，可按策略卖出"
                            )
                            cell.setToolTip(tip)
                    elif key == "exit_signal" and snap is not None:
                        cell.setToolTip(snap.exit_signal_tooltip)
                    if fg:
                        cell.setForeground(QtGui.QColor(fg))
                    else:
                        cell.setData(QtCore.Qt.ItemDataRole.ForegroundRole, None)
                if snap is not None and snap.signal_snapshot is not None:
                    symbol_cell = self._table.item(row, 0)
                    if symbol_cell is not None:
                        symbol_cell.setToolTip(snap.signal_snapshot.tooltip)

            self._rendered_symbols = rendered
            self._refresh_stats()
        finally:
            self._building = False
