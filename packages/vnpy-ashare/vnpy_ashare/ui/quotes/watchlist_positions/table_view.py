"""自选持仓区表格体（QTableView + Model + 统计 + 行渲染）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.trading.position import PositionRecord, position_row_sort_key, position_t1_locked
from vnpy_ashare.domain.trading.signal_snapshot import signal_missing_kline
from vnpy_ashare.quotes.misc.position_anomaly import (
    format_anomaly_tags,
    is_position_anomaly,
    position_anomaly_reasons,
    position_anomaly_score,
)
from vnpy_ashare.services.position import PositionService
from vnpy_ashare.services.signals.runtime import signal_cell_color
from vnpy_ashare.trading.exit.exit_display import (
    exit_rule_cell_color,
    format_exit_rules_summary,
    format_exit_rules_tooltip,
)
from vnpy_ashare.trading.risk.book_pnl import format_book_pnl_hint, summarize_book_pnl
from vnpy_ashare.trading.risk.metrics import read_total_capital
from vnpy_ashare.trading.risk.plan_position import (
    compute_position_actual_pct,
    format_plan_vs_actual_cell,
)
from vnpy_ashare.ui.quotes.table.model import QuoteCell
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_ashare.ui.quotes.watchlist_positions.position_panel_model import PositionPanelTableModel
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import market_colors

PANEL_COLUMNS = (
    ("symbol", "代码"),
    ("name", "名称"),
    ("cost_price", "成本价"),
    ("volume", "持仓量(股)"),
    ("buy_date", "买入日"),
    ("last_price", "现价"),
    ("pnl", "浮盈(元)"),
    ("pnl_pct", "浮盈%"),
    ("plan_pct", "计划/实际%"),
    ("t1_status", "T+1"),
    ("exit_signal", "退出信号"),
    ("exit_rules", "隔日规则"),
    ("ref_sell_price", "参考卖价"),
)

_EMPTY_TEXT = f"暂无持仓。请在自选表选中标的后点击持仓区「添加」（最多 {PositionService.max_items} 只）。"
_FILTER_EMPTY_TEXT = "当前筛选无匹配标的，再次点击统计项可取消筛选。"

_COLUMN_WIDTHS = {
    "symbol": 72,
    "name": 88,
    "cost_price": 72,
    "volume": 88,
    "buy_date": 88,
    "last_price": 72,
    "pnl": 80,
    "pnl_pct": 72,
    "plan_pct": 96,
    "t1_status": 72,
    "exit_signal": 72,
    "exit_rules": 120,
    "ref_sell_price": 80,
}


class PositionPanelTableView(QtWidgets.QWidget):
    """持仓区表格：列表渲染、增量更新、统计筛选。"""

    row_activated = QtCore.Signal(str)
    row_selected = QtCore.Signal(str)

    def __init__(self, page: WatchlistHost, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._page = page
        self._building = False
        self._suppress_selection_signal = False
        self._rendered_symbols: list[str] = []
        self._filter: str | None = None
        self._updated_at = ""
        self._model = PositionPanelTableModel(self)
        self._build_ui()
        self._sync_table_columns()

    # ── 公开 API ──────────────────────────────────────────────

    def set_updated_at(self, text: str) -> None:
        self._updated_at = text.strip()

    def mark_building(self, building: bool) -> None:
        self._building = building

    def selected_vt_symbol(self) -> str:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return ""
        return self._model.vt_symbol_at(rows[0].row())

    def highlight_symbol(self, vt_symbol: str) -> None:
        if not vt_symbol:
            return
        row = self._model.row_for_vt_symbol(vt_symbol)
        if row < 0:
            return
        self._suppress_selection_signal = True
        self._table.selectRow(row)
        self._suppress_selection_signal = False

    def render_table(self) -> None:
        if self._building:
            return
        self._building = True
        try:
            if not self._records():
                self._show_empty(_EMPTY_TEXT, refresh_stats=False)
                self._stats_label.setText("")
                self._rendered_symbols = []
                return

            records = self._sorted_display_records()
            if not records:
                self._show_empty(_FILTER_EMPTY_TEXT)
                self._rendered_symbols = []
                return

            self._empty_label.setVisible(False)
            self._table.setVisible(True)

            total_capital = read_total_capital()
            tokens = theme_manager().tokens()
            colors = market_colors(tokens)
            warning_color = tokens.semantic_warning
            highlight_bg = tokens.nav_hover_bg
            panel_filter = self._filter

            if [record.vt_symbol for record in records] == self._rendered_symbols:
                for row, record in enumerate(records):
                    cells = _build_position_row_cells(
                        self._page,
                        record,
                        total_capital=total_capital,
                        colors=colors,
                        warning_color=warning_color,
                        highlight_bg=highlight_bg,
                        panel_filter=panel_filter,
                    )
                    self._model.apply_row(row, cells)
            else:
                vt_symbols = [record.vt_symbol for record in records]
                rows = [
                    _build_position_row_cells(
                        self._page,
                        record,
                        total_capital=total_capital,
                        colors=colors,
                        warning_color=warning_color,
                        highlight_bg=highlight_bg,
                        panel_filter=panel_filter,
                    )
                    for record in records
                ]
                self._model.set_rows_with_symbols(vt_symbols, rows)
                self._rendered_symbols = vt_symbols

            self._refresh_stats()
        finally:
            self._building = False

    def update_rows_for_tickflow_symbols(self, tickflow_symbols: set[str], *, enabled: bool, expanded: bool) -> None:
        if not tickflow_symbols or not enabled or not expanded:
            return
        if not self._table.isVisible() or self._building:
            return
        if not self._records() or not self._rendered_symbols:
            return

        records = self._sorted_display_records()
        if [record.vt_symbol for record in records] != self._rendered_symbols:
            self.render_table()
            return

        total_capital = read_total_capital()
        tokens = theme_manager().tokens()
        colors = market_colors(tokens)
        warning_color = tokens.semantic_warning
        highlight_bg = tokens.nav_hover_bg
        panel_filter = self._filter

        self._building = True
        try:
            for row, record in enumerate(records):
                item = self._page.find_stock_item(record.vt_symbol)
                if item is None or item.tickflow_symbol not in tickflow_symbols:
                    continue
                cells = _build_position_row_cells(
                    self._page,
                    record,
                    total_capital=total_capital,
                    colors=colors,
                    warning_color=warning_color,
                    highlight_bg=highlight_bg,
                    panel_filter=panel_filter,
                )
                self._model.apply_row(row, cells)
        finally:
            self._building = False

    # ── 数据访问 ──────────────────────────────────────────────

    def _records(self) -> list[PositionRecord]:
        service = self._page._get_position_service()
        if service is None:
            return []
        return service.get_items()

    def _quote_for_record(self, record: PositionRecord):
        item = self._page.find_stock_item(record.vt_symbol)
        if item is None:
            return None
        return self._page.quote_map.get(item.tickflow_symbol)

    def _anomaly_context(self, record: PositionRecord):
        snap = self._page.position_cache.get(record.vt_symbol)
        quote = self._quote_for_record(record)
        reasons = position_anomaly_reasons(snap=snap, quote=quote)
        return snap, quote, reasons

    def _anomaly_kwargs(self, record: PositionRecord) -> dict:
        snap, quote, _ = self._anomaly_context(record)
        return {"snap": snap, "quote": quote}

    def _filtered_records(self) -> list[PositionRecord]:
        records = self._records()
        if not self._filter:
            return records
        if self._filter == "anomaly":
            matched = [record for record in records if is_position_anomaly(**self._anomaly_kwargs(record))]
            return sorted(
                matched,
                key=lambda record: (
                    -position_anomaly_score(self._anomaly_context(record)[2]),
                    position_row_sort_key(self._page.position_cache[record.vt_symbol])
                    if record.vt_symbol in self._page.position_cache
                    else (9, 0.0, record.vt_symbol),
                ),
            )
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

    def _sorted_display_records(self) -> list[PositionRecord]:
        records = self._filtered_records()
        if self._filter == "anomaly":
            return records
        return sorted(
            records,
            key=lambda record: (
                position_row_sort_key(self._page.position_cache[record.vt_symbol])
                if record.vt_symbol in self._page.position_cache
                else (9, 0.0, record.vt_symbol)
            ),
        )

    def _show_empty(self, text: str, *, refresh_stats: bool = True) -> None:
        self._table.setVisible(False)
        self._empty_label.setText(text)
        self._empty_label.setVisible(True)
        self._model.clear_rows()
        if refresh_stats:
            self._refresh_stats()

    # ── 统计条 ───────────────────────────────────────────────

    def _stats_link(self, key: str, label: str, color: str) -> str:
        active = self._filter == key
        style = f"color:{color};text-decoration:{'underline' if active else 'none'}"
        return f'<a href="{key}" style="{style}">{label}</a>'

    def _refresh_stats(self) -> None:
        colors = market_colors(theme_manager().tokens())
        warning_color = theme_manager().tokens().semantic_warning
        records = self._records()
        sell_count = t1_count = missing_count = anomaly_count = 0
        total_pnl = 0.0
        has_pnl = False
        for record in records:
            snap = self._page.position_cache.get(record.vt_symbol)
            quote = self._quote_for_record(record)
            if is_position_anomaly(snap=snap, quote=quote):
                anomaly_count += 1
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
        book_hint = format_book_pnl_hint(summarize_book_pnl(self._page.position_cache))
        parts = [
            f"持仓 {len(records)}",
            f"总浮盈 {pnl_text}",
        ]
        if book_hint:
            parts.append(book_hint)
        parts.extend(
            [
                self._stats_link("anomaly", f"异动 {anomaly_count}", warning_color),
                self._stats_link("sell", f"卖出信号 {sell_count}", colors.fall),
                self._stats_link("t1", f"T+1 {t1_count}", colors.flat),
                self._stats_link("missing", f"缺日K {missing_count}", warning_color),
            ]
        )
        self._stats_label.setText(" · ".join(parts) + updated)

    def _on_stats_filter_link(self, link: str) -> None:
        key = link.strip()
        if self._filter == key:
            self._filter = None
        else:
            self._filter = key
        self.render_table()

    # ── 选择 ─────────────────────────────────────────────────

    def _on_selection_changed(self) -> None:
        if self._suppress_selection_signal or self._building:
            return
        vt_symbol = self.selected_vt_symbol()
        if vt_symbol:
            self.row_selected.emit(vt_symbol)

    def _on_cell_activated(self, index: QtCore.QModelIndex) -> None:
        if not index.isValid():
            return
        vt_symbol = self._model.vt_symbol_at(index.row())
        if vt_symbol:
            self.row_activated.emit(vt_symbol)

    # ── UI 构建 ─────────────────────────────────────────────

    def _sync_table_columns(self) -> None:
        headers = [label for _, label in PANEL_COLUMNS]
        self._model.set_headers(headers)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setMinimumHeight(140)
        header_view = self._table.horizontalHeader()
        for col, (key, _label) in enumerate(PANEL_COLUMNS):
            header_view.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Interactive)
            self._table.setColumnWidth(col, _COLUMN_WIDTHS.get(key, 72))

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
        self._table.setObjectName("WatchlistPositionTable")
        self._table.setModel(self._model)
        self._table.doubleClicked.connect(self._on_cell_activated)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        root.addWidget(self._table, stretch=1)

        self._empty_label = QtWidgets.QLabel(_EMPTY_TEXT, self)
        self._empty_label.setObjectName("BottomBarMeta")
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setVisible(False)
        root.addWidget(self._empty_label)


def _row_values(page: WatchlistHost, record: PositionRecord, *, total_capital: float | None):
    snap = page.position_cache.get(record.vt_symbol)
    item = page.find_stock_item(record.vt_symbol)
    quote = page.quote_map.get(item.tickflow_symbol) if item is not None else None
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
    market_value = None
    if snap is not None and snap.market_value is not None:
        market_value = snap.market_value
    elif last_price is not None and record.volume > 0:
        market_value = last_price * record.volume
    actual_pct = compute_position_actual_pct(
        market_value=market_value,
        total_capital=total_capital,
    )
    plan_cell, plan_tooltip = format_plan_vs_actual_cell(
        plan_pct=record.plan_pct,
        actual_pct=actual_pct,
    )
    values["plan_pct"] = plan_cell
    if snap is None:
        values["pnl"] = "—"
        values["pnl_pct"] = "—"
        values["exit_signal"] = "待计算"
        values["exit_rules"] = "—"
        values["ref_sell_price"] = "—"
        return values, snap, quote, plan_tooltip
    pnl = snap.unrealized_pnl
    values["pnl"] = f"{pnl:+.2f}" if pnl is not None else "—"
    pnl_pct = snap.unrealized_pnl_pct
    values["pnl_pct"] = f"{pnl_pct:+.2f}%" if pnl_pct is not None else "—"
    values["t1_status"] = snap.t1_status_label
    values["exit_signal"] = snap.exit_signal_label
    values["exit_rules"] = format_exit_rules_summary(snap.exit_rules)
    ref_sell = snap.exit_ref_price
    values["ref_sell_price"] = f"{ref_sell:.2f}" if ref_sell is not None else "—"
    return values, snap, quote, plan_tooltip


def _build_position_row_cells(
    page: WatchlistHost,
    record: PositionRecord,
    *,
    total_capital: float | None,
    colors,
    warning_color: str,
    highlight_bg: str,
    panel_filter: str | None,
) -> list[QuoteCell]:
    values, snap, quote, plan_tooltip = _row_values(page, record, total_capital=total_capital)
    snap_cache = page.position_cache.get(record.vt_symbol)
    quote_for_anomaly = None
    item = page.find_stock_item(record.vt_symbol)
    if item is not None:
        quote_for_anomaly = page.quote_map.get(item.tickflow_symbol)
    anomaly_reasons = position_anomaly_reasons(snap=snap_cache, quote=quote_for_anomaly)
    row_anomaly = bool(anomaly_reasons)
    anomaly_tip = format_anomaly_tags(anomaly_reasons)
    buy_date = values.get("buy_date", "—")
    t1_locked = snap.t1_locked if snap is not None else (position_t1_locked(buy_date) if buy_date != "—" else False)
    config = page.position_config.normalized().effective_signal_config(page.signal_config)
    row_bg = highlight_bg if row_anomaly and panel_filter != "anomaly" else None

    cells: list[QuoteCell] = []
    for key, _label in PANEL_COLUMNS:
        text = values.get(key, "—")
        fg = None
        tooltip = None
        if key == "pnl" and snap is not None and snap.unrealized_pnl is not None:
            fg = colors.rise if snap.unrealized_pnl >= 0 else colors.fall
        elif key == "pnl_pct" and snap is not None and snap.unrealized_pnl_pct is not None:
            fg = colors.rise if snap.unrealized_pnl_pct >= 0 else colors.fall
        elif key == "t1_status":
            if t1_locked:
                fg = warning_color
            elif snap is not None:
                fg = colors.flat
            if snap is not None:
                tooltip = snap.t1_status_tooltip
            elif buy_date != "—":
                tooltip = (
                    f"买入日 {buy_date}：当日买入不可卖（A 股 T+1）"
                    if t1_locked
                    else f"买入日 {buy_date}：已过 T+1，可按策略卖出"
                )
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
            tooltip = snap.exit_signal_tooltip
        elif key == "exit_rules" and snap is not None:
            fg = exit_rule_cell_color(snap.exit_rules, colors=colors, warning_color=warning_color)
            if snap.exit_rules:
                tooltip = format_exit_rules_tooltip(snap.exit_rules)
        elif key == "plan_pct" and plan_tooltip:
            tooltip = plan_tooltip
        elif key == "symbol":
            if snap is not None and snap.signal_snapshot is not None:
                tip = snap.signal_snapshot.tooltip
                if anomaly_tip:
                    tip = f"{tip}\n异动：{anomaly_tip}" if tip else f"异动：{anomaly_tip}"
                tooltip = tip
            elif anomaly_tip:
                tooltip = f"异动：{anomaly_tip}"

        cells.append(
            QuoteCell(
                text=text,
                color=fg or None,
                bg_color=row_bg,
                tooltip=tooltip,
            )
        )
    return cells
