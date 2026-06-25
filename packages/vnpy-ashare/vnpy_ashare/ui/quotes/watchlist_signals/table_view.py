"""自选信号区表格体（QTableView + Model + 统计 + 行渲染）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.preferences.signal_panel_columns import (
    normalize_visible_optional_keys,
    resolve_signal_panel_columns,
)
from vnpy_ashare.config.preferences.watchlist_signal import (
    SIGNAL_PANEL_MAX_SYMBOLS,
    load_signal_panel_columns,
    save_signal_panel_columns,
)
from vnpy_ashare.domain.symbols.stock import lookup_by_vt_symbol, parse_stock_symbol
from vnpy_ashare.domain.trading.signal_snapshot import (
    SIGNAL_STRENGTH_STRONG,
    SignalSnapshot,
    signal_is_fresh,
    signal_is_strong,
    signal_missing_kline,
    signal_row_sort_key,
)
from vnpy_ashare.domain.trading.stock_continuation import format_outlook_compact
from vnpy_ashare.services.signals.runtime import (
    build_price_field_explanations,
    build_runtime_signal_hints,
    format_strength_breakdown,
    resolve_display_anchor_prices,
    signal_cell_color,
    signal_cell_text,
)
from vnpy_ashare.ui.quotes._host_widget import as_qwidget
from vnpy_ashare.ui.quotes.table.model import QuoteCell
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_ashare.ui.quotes.watchlist_signals.signal_info_delegate import SignalInfoColumnDelegate
from vnpy_ashare.ui.quotes.watchlist_signals.signal_panel_model import SignalPanelTableModel
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import market_colors, pct_change_color

_DETAIL_COLUMN_KEYS = ("signal_date", "signal_reason")

_EMPTY_LIST_TEXT = f"暂无监控标的。请在上方自选表多选后右键「加入信号区」（最多 {SIGNAL_PANEL_MAX_SYMBOLS} 只）。"
_FILTER_EMPTY_TEXT = "当前筛选无匹配标的，再次点击统计项可取消筛选。"


class SignalPanelTableView(QtWidgets.QWidget):
    """信号区表格：列表渲染、增量更新、统计筛选。"""

    row_activated = QtCore.Signal(str)
    row_selected = QtCore.Signal(str)

    def __init__(self, page: WatchlistHost, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._page = page
        self._building = False
        self._suppress_selection_signal = False
        self._rendered_symbols: list[str] = []
        self._signal_filter: str | None = None
        self._symbols: list[str] = []
        self._updated_at = ""
        self._visible_column_keys: list[str] = load_signal_panel_columns()
        self._column_menu: QtWidgets.QMenu | None = None
        self._model = SignalPanelTableModel(self)
        self._info_delegate: SignalInfoColumnDelegate | None = None
        self._build_ui()
        self._sync_table_columns(reset_rows=False)

    # ── 属性 / 公开方法 ──────────────────────────────────────

    @property
    def signal_filter(self) -> str | None:
        return self._signal_filter

    @signal_filter.setter
    def signal_filter(self, value: str | None) -> None:
        self._signal_filter = value

    def visible_column_keys(self) -> list[str]:
        return list(self._visible_column_keys)

    def set_visible_column_keys(self, keys: list[str]) -> None:
        self._visible_column_keys = normalize_visible_optional_keys(keys)
        save_signal_panel_columns(self._visible_column_keys)
        self._sync_table_columns(reset_rows=True)
        self.render_table()

    def set_symbols(self, symbols: list[str]) -> None:
        self._symbols = list(symbols)

    def set_updated_at(self, text: str) -> None:
        self._updated_at = text.strip()
        self._refresh_stats()

    def set_visible(self, visible: bool) -> None:
        self.setVisible(visible)

    def set_enabled(self, enabled: bool) -> None:
        self._table.setEnabled(enabled)

    def is_expanded(self) -> bool:
        return self.isVisible()

    def mark_building(self, building: bool) -> None:
        self._building = building

    def select_all(self) -> None:
        self._table.selectAll()

    def clear_selection(self) -> None:
        self._table.clearSelection()

    # ── 渲染 ─────────────────────────────────────────────────

    def render_table(self) -> None:
        has_symbols = bool(self._symbols)
        display_symbols = self._sorted_display_symbols()
        if not has_symbols:
            self._rendered_symbols = []
            self._table.setVisible(False)
            self._empty_label.setText(_EMPTY_LIST_TEXT)
            self._empty_label.setVisible(True)
            self._model.clear_rows()
            self._refresh_stats()
            return
        if not display_symbols:
            self._rendered_symbols = []
            self._table.setVisible(False)
            self._empty_label.setText(_FILTER_EMPTY_TEXT)
            self._empty_label.setVisible(True)
            self._model.clear_rows()
            self._refresh_stats()
            return
        self._empty_label.setVisible(False)
        self._table.setVisible(True)
        if display_symbols == self._rendered_symbols:
            self._update_row_cells(display_symbols)
        elif (
            len(display_symbols) == len(self._rendered_symbols)
            and set(display_symbols) == set(self._rendered_symbols)
            and self._model.reorder_symbols(display_symbols)
        ):
            self._update_row_cells(display_symbols)
        else:
            self._rebuild_table(display_symbols)
        self._rendered_symbols = list(display_symbols)
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
            row = self._model.row_for_vt_symbol(target)
            if row >= 0:
                self._table.selectRow(row)
                return
            self._table.clearSelection()
        finally:
            self._suppress_selection_signal = False

    def sync_highlight_from_page(self) -> None:
        item = self._page.current_item
        if item is None:
            return
        if item.vt_symbol in self._symbols:
            self.highlight_symbol(item.vt_symbol)

    def selected_vt_symbols(self) -> list[str]:
        rows = self._table.selectionModel().selectedRows()
        symbols: list[str] = []
        for model_index in rows:
            vt = self._model.vt_symbol_at(model_index.row())
            if vt:
                symbols.append(vt)
        return symbols

    def update_rows_for_tickflow_symbols(self, tickflow_symbols: set[str]) -> None:
        if not self._symbols or not tickflow_symbols or not self.isVisible():
            return
        if not self._table.isVisible():
            return
        page = self._page
        display_symbols = self._sorted_display_symbols()
        if not display_symbols:
            return
        self._building = True
        try:
            for row, vt_symbol in enumerate(display_symbols):
                item, quote = _resolve_row_item_and_quote(page, vt_symbol)
                if item is None or item.tickflow_symbol not in tickflow_symbols:
                    continue
                cells = _build_signal_row_cells(
                    page,
                    vt_symbol,
                    panel_columns=self._panel_columns(),
                )
                self._model.apply_row(row, cells)
        finally:
            self._building = False

    # ── 内部：表格列配置 ─────────────────────────────────────

    def _panel_columns(self) -> tuple[tuple[str, str], ...]:
        return resolve_signal_panel_columns(self._visible_column_keys)

    def _info_column_index(self) -> int:
        return len(self._panel_columns())

    def _sync_table_columns(self, *, reset_rows: bool) -> None:
        columns = self._panel_columns()
        info_index = len(columns)
        headers = [label for _, label in columns] + [""]
        self._model.set_headers(headers)

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
        if self._info_delegate is not None:
            self._table.setItemDelegateForColumn(info_index, self._info_delegate)
        default_widths = {
            "symbol": 72,
            "name": 88,
            "signal": 56,
            "signal_date": 88,
            "volume_ratio_5d": 64,
            "ma_gap_pct": 72,
            "ref_buy_price": 80,
            "ref_sell_price": 80,
            "dist_buy_pct": 72,
            "dist_sell_pct": 72,
            "signal_strength": 56,
            "relative_index_pct": 80,
            "continuation_pattern": 88,
            "outlook_compact": 96,
        }
        for col, (key, _label) in enumerate(columns):
            header_view.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Interactive)
            self._table.setColumnWidth(col, default_widths.get(key, 72))
        if reset_rows:
            self._rendered_symbols = []
            self._model.clear_rows()

    # ── 内部：表格重建 / 更新 ────────────────────────────────

    def _sorted_display_symbols(self) -> list[str]:
        symbols = self._filtered_symbols()
        return sorted(
            symbols,
            key=lambda vt: signal_row_sort_key(lookup_by_vt_symbol(self._page.signal_cache, vt)),
            reverse=True,
        )

    def _rebuild_table(self, display_symbols: list[str]) -> None:
        self._building = True
        try:
            rows = [
                _build_signal_row_cells(self._page, vt_symbol, panel_columns=self._panel_columns())
                for vt_symbol in display_symbols
            ]
            self._model.set_rows_with_symbols(display_symbols, rows)
        finally:
            self._building = False

    def _update_row_cells(self, display_symbols: list[str]) -> None:
        self._building = True
        try:
            for vt_symbol in display_symbols:
                row = self._model.row_for_vt_symbol(vt_symbol)
                if row < 0:
                    continue
                cells = _build_signal_row_cells(
                    self._page,
                    vt_symbol,
                    panel_columns=self._panel_columns(),
                )
                self._model.apply_row(row, cells)
        finally:
            self._building = False

    def _on_info_row_requested(self, row: int) -> None:
        vt_symbol = self._model.vt_symbol_at(row)
        if not vt_symbol:
            return
        self._suppress_selection_signal = True
        try:
            self.show_signal_reason(vt_symbol)
        finally:
            QtCore.QTimer.singleShot(0, self._release_selection_suppress)

    def _release_selection_suppress(self) -> None:
        self._suppress_selection_signal = False

    def show_signal_reason(self, vt_symbol: str) -> None:
        self._show_signal_reason_dialog(vt_symbol)

    def _show_signal_reason_dialog(self, vt_symbol: str) -> None:
        page = self._page
        item, quote = _resolve_row_item_and_quote(page, vt_symbol)
        snapshot = lookup_by_vt_symbol(page.signal_cache, vt_symbol)
        continuation = lookup_by_vt_symbol(page.continuation_cache, vt_symbol)
        values = _compute_row_values(
            item,
            snapshot,
            quote,
            bar_end_date=_bar_end_date_for(page, vt_symbol),
            config=page.signal_config.normalized(),
            panel_columns=self._panel_columns(),
            continuation=continuation,
        )
        title_name = values.get("name") or vt_symbol
        detail = _compute_row_tooltip(
            snapshot,
            values,
            quote=quote,
            vt_symbol=vt_symbol,
            config=page.signal_config.normalized(),
            position_cache=page.position_cache,
            continuation=continuation,
        )
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
        if continuation is not None and continuation.sector_id:
            sector_btn = buttons.addButton("板块资金", QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
            sector_btn.clicked.connect(lambda _checked=False, sector_id=continuation.sector_id: self._open_sector_flow(sector_id))
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        close_btn = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def _open_sector_flow(self, sector_id: str) -> None:
        cleaned = str(sector_id or "").strip()
        if not cleaned:
            return
        widget: QtWidgets.QWidget | None = as_qwidget(self._page)
        while widget is not None:
            if hasattr(widget, "open_sector_flow"):
                widget.open_sector_flow([cleaned], tab="outlook", sector_kind="industry")
                return
            widget = widget.parentWidget()

    # ── 内部：筛选 ───────────────────────────────────────────

    def _filtered_symbols(self) -> list[str]:
        if not self._signal_filter:
            return list(self._symbols)
        filtered: list[str] = []
        for vt in self._symbols:
            snap = lookup_by_vt_symbol(self._page.signal_cache, vt)
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

    # ── 内部：统计条 ─────────────────────────────────────────

    def _stats_link(self, key: str, label: str, color: str) -> str:
        active = self._signal_filter == key
        style = f"color:{color};text-decoration:{'underline' if active else 'none'}"
        return f'<a href="{key}" style="{style}">{label}</a>'

    def _refresh_stats(self) -> None:
        colors = market_colors(theme_manager().tokens())
        warning_color = theme_manager().tokens().semantic_warning
        buy_n = sell_n = hold_n = missing_n = fresh_n = strong_n = held_n = 0
        for vt in self._symbols:
            snap = lookup_by_vt_symbol(self._page.signal_cache, vt)
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
        elif self._symbols:
            signals = getattr(self._page, "_signals", None)
            refreshing = bool(signals is not None and signals.is_refreshing)
            waiting = bool(signals is not None and getattr(signals, "is_waiting_for_service", False))
            missing = any(lookup_by_vt_symbol(self._page.signal_cache, vt) is None for vt in self._symbols)
            if refreshing:
                parts.append("计算中")
            elif waiting:
                parts.append("服务初始化中")
            elif missing:
                parts.append("待计算")
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
        self.render_table()

    # ── 内部：选择 ───────────────────────────────────────────

    def _on_table_selection_changed(self) -> None:
        if self._building or self._suppress_selection_signal:
            return
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        vt = self._model.vt_symbol_at(rows[0].row())
        if vt:
            self.row_selected.emit(vt)

    def _on_cell_activated(self, index: QtCore.QModelIndex) -> None:
        if not index.isValid():
            return
        vt = self._model.vt_symbol_at(index.row())
        if vt:
            self.row_activated.emit(vt)

    # ── UI 构建 ─────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self._stats_label = QtWidgets.QLabel("", self)
        self._stats_label.setObjectName("StatsLabel")
        self._stats_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self._stats_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextBrowserInteraction)
        self._stats_label.setOpenExternalLinks(False)
        self._stats_label.linkActivated.connect(self._on_stats_filter_link)
        root.addWidget(self._stats_label)

        self._table = QtWidgets.QTableView(self)
        self._table.setObjectName("WatchlistSignalTable")
        self._table.setModel(self._model)
        self._info_delegate = SignalInfoColumnDelegate(self._table)
        self._info_delegate.reason_requested.connect(self._on_info_row_requested)
        self._table.doubleClicked.connect(self._on_cell_activated)
        self._table.selectionModel().selectionChanged.connect(self._on_table_selection_changed)
        root.addWidget(self._table, stretch=1)

        self._empty_label = QtWidgets.QLabel(_EMPTY_LIST_TEXT, self)
        self._empty_label.setObjectName("BottomBarMeta")
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        root.addWidget(self._empty_label)


# ── 行渲染纯函数 ────────────────────────────────────────────


def _bar_end_date_for(page: WatchlistHost, vt_symbol: str) -> str | None:
    from vnpy_ashare.services.bar import format_meta_date

    item = page.find_stock_item(vt_symbol)
    if item is None:
        return None
    meta = page.bar_meta.get((item.symbol, item.exchange))
    if meta is None or meta.end is None:
        return None
    return format_meta_date(meta.end)


def _build_signal_row_cells(
    page: WatchlistHost,
    vt_symbol: str,
    *,
    panel_columns: tuple[tuple[str, str], ...],
) -> list[QuoteCell]:
    item, quote = _resolve_row_item_and_quote(page, vt_symbol)
    snapshot = lookup_by_vt_symbol(page.signal_cache, vt_symbol)
    missing_kline = signal_missing_kline(snapshot)
    bar_end_date = _bar_end_date_for(page, vt_symbol)
    continuation = lookup_by_vt_symbol(page.continuation_cache, vt_symbol)
    values = _compute_row_values(
        item,
        snapshot,
        quote,
        bar_end_date=bar_end_date,
        config=page.signal_config.normalized(),
        panel_columns=panel_columns,
        continuation=continuation,
    )
    tooltip = _compute_row_tooltip(
        snapshot,
        values,
        quote=quote,
        vt_symbol=vt_symbol,
        config=page.signal_config.normalized(),
        position_cache=page.position_cache,
        continuation=continuation,
    )
    strength_tooltip = format_strength_breakdown(snapshot)
    colors = market_colors(theme_manager().tokens())
    warning_color = theme_manager().tokens().semantic_warning
    config = page.signal_config.normalized()

    cells: list[QuoteCell] = []
    for key, _label in panel_columns:
        text = values.get(key, "—")
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
        elif key in {"continuation_pattern", "outlook_compact"} and continuation is not None:
            bias_value = 0.0
            if continuation.outlook_days:
                bias = continuation.outlook_days[0].bias
                if bias == "偏多":
                    bias_value = 1.0
                elif bias == "偏空":
                    bias_value = -1.0
            fg = pct_change_color(bias_value, theme_manager().tokens())
        cell_tooltip = strength_tooltip if key == "signal_strength" and strength_tooltip else tooltip
        cells.append(QuoteCell(text=text, color=fg or None, tooltip=cell_tooltip))

    cells.append(QuoteCell(text="理由", tooltip="查看信号理由"))
    return cells


def _resolve_row_item_and_quote(page: WatchlistHost, vt_symbol: str):
    item = page.find_stock_item(vt_symbol)
    if item is None:
        item = parse_stock_symbol(vt_symbol)
    quote = page.quote_map.get(item.tickflow_symbol) if item is not None else None
    return item, quote


def _resolve_signal_row_name(item, quote) -> str:
    if quote is not None and quote.name:
        text = str(quote.name).strip()
        if text:
            return text
    if item is not None and item.name:
        text = str(item.name).strip()
        if text:
            return text
    return "—"


def _compute_row_values(
    item,
    snapshot: SignalSnapshot | None,
    quote,
    *,
    bar_end_date: str | None = None,
    config,
    panel_columns: tuple[tuple[str, str], ...],
    continuation=None,
) -> dict[str, str]:
    values: dict[str, str] = {
        "symbol": item.symbol if item is not None else "—",
        "name": _resolve_signal_row_name(item, quote),
    }
    if snapshot is None:
        for col_key, _ in panel_columns:
            if col_key not in values:
                values[col_key] = "—"
        for key in _DETAIL_COLUMN_KEYS:
            values[key] = "—"
        if item is not None:
            values["signal_reason"] = "待计算"
        return values
    cell_kwargs = {
        "quote": quote,
        "bar_end_date": bar_end_date,
        "slow_window": config.slow_window,
        "fast_window": config.fast_window,
    }
    for key, _ in panel_columns:
        if key in {"symbol", "name"}:
            continue
        if key == "continuation_pattern":
            values[key] = continuation.headline_pattern if continuation else "—"
            continue
        if key == "outlook_compact":
            values[key] = format_outlook_compact(continuation)
            continue
        text, _ = signal_cell_text(key, snapshot, **cell_kwargs)
        values[key] = text
    for key in _DETAIL_COLUMN_KEYS:
        text, _ = signal_cell_text(key, snapshot, **cell_kwargs)
        values[key] = text
    if snapshot.warnings:
        values["signal_reason"] = snapshot.warnings[0]
    return values


def _compute_row_tooltip(
    snapshot: SignalSnapshot | None,
    values: dict[str, str],
    *,
    quote,
    vt_symbol: str = "",
    config,
    position_cache: dict,
    continuation=None,
) -> str:
    lines: list[str] = []
    if snapshot is None:
        reason = values.get("signal_reason")
        if reason and reason != "—":
            lines.append(reason)
        lines.extend(_position_tooltip_lines(position_cache, vt_symbol, None))
        return "\n".join(lines)
    signal_date = values.get("signal_date") or snapshot.signal_date or "—"
    if signal_date != "—":
        lines.append(f"信号日：{signal_date}")
    if snapshot.as_of:
        lines.append(f"K 线截止：{snapshot.as_of}")
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
    lines.extend(_position_tooltip_lines(position_cache, vt_symbol, snapshot))
    breakdown = format_strength_breakdown(snapshot)
    if breakdown:
        lines.append("")
        lines.append("【强度分解】")
        lines.append(breakdown)
    if continuation is not None and continuation.headline_pattern not in {"", "—"}:
        lines.append("")
        lines.append("【个股延续】")
        if continuation.rationale:
            lines.append(continuation.rationale)
        if continuation.outlook_days:
            tags = " / ".join(f"T+{index + 1}{day.bias}" for index, day in enumerate(continuation.outlook_days))
            lines.append(f"未来3日：{tags}")
        lines.append(continuation.disclaimer)
    if continuation is not None and continuation.sector_name:
        lines.append("")
        lines.append("【板块环境】")
        sector_line = continuation.sector_name
        if continuation.sector_pattern:
            sector_line += f"：{continuation.sector_pattern}"
        if continuation.sector_outlook_compact and continuation.sector_outlook_compact != "—":
            sector_line += f" {continuation.sector_outlook_compact}"
        lines.append(sector_line)
        lines.append("与个股延续独立，统计情景，非资金预测")
    if snapshot is not None:
        reason = values.get("signal_reason") or snapshot.reason_summary
        if reason and reason != "—":
            lines.append(f"理由：{reason}")
        if snapshot.tooltip:
            if lines:
                lines.append("")
            lines.append(snapshot.tooltip)
    return "\n".join(line for line in lines if line)


def _position_tooltip_lines(
    position_cache: dict,
    vt_symbol: str,
    snapshot: SignalSnapshot | None,
) -> list[str]:
    pos = position_cache.get(vt_symbol)
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
