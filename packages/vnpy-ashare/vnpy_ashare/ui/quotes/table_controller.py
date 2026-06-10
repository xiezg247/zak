"""行情表格：列配置、渲染、筛选与选中。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.data.bar_health import (
    BarHealthStatus,
    format_meta_datetime,
    list_status,
    status_label,
)
from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.ui.quotes.quote_columns import (
    QUOTE_TABLE_COLUMNS,
    build_local_data_row,
    build_quote_row,
    quote_column_index,
)
from vnpy_ashare.ui.quotes.quotes_config import (
    ALL_TAIL_COLUMNS,
    DEFAULT_WATCHLIST_COLUMNS,
    MARKET_VISIBLE_COLUMNS,
    MAX_DISPLAY_ROWS,
    STATS_DEBOUNCE_MS,
)
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import market_colors, quote_change_color

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.quotes_page import QuotesPage

STATUS_OK_COLOR = "#3ddc84"
STATUS_STALE_COLOR = "#f0b429"
STATUS_GAP_COLOR = "#ff5c5c"


class TableController:
    """QuotesPage 表格与列配置。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page
        self.visible_columns: list[str] = []
        self.visible_tail_columns: list[str] = []
        self._symbol_row_index: dict[str, int] | None = None
        self._stats_timer = QtCore.QTimer(page)
        self._stats_timer.setSingleShot(True)
        self._stats_timer.setInterval(STATS_DEBOUNCE_MS)
        self._stats_timer.timeout.connect(self.update_stats)

    @property
    def _p(self) -> QuotesPage:
        return self._page

    def _model(self):
        return self._p.quote_table_model

    def _view(self) -> QtWidgets.QTableView:
        return self._p.market_table

    def init_columns(self) -> None:
        page = self._p
        if page.config.column_configurable:
            all_keys = [c.key for c in QUOTE_TABLE_COLUMNS]
            if page.page_name == "自选":
                default_main = [k for k in DEFAULT_WATCHLIST_COLUMNS if k in all_keys]
            else:
                default_main = [k for k in MARKET_VISIBLE_COLUMNS if k in all_keys]
            for required in ("index", "symbol", "name"):
                if required in all_keys and required not in default_main:
                    default_main.insert(0, required)
            self.visible_columns = default_main
            self.visible_tail_columns = self._default_tail_columns()
        else:
            self.visible_columns = [c.key for c in QUOTE_TABLE_COLUMNS]
            self.visible_tail_columns = self._default_tail_columns()
        self.restore_column_config()

    def _default_tail_columns(self) -> list[str]:
        page = self._p
        if page.config.use_local_table:
            return []
        if page.config.show_fill_button and not page.config.use_local_table:
            return ["start", "end", "count", "status"]
        if page.config.show_local_column:
            return ["local"]
        return ["local"]

    def build_visible_headers(self) -> list[str]:
        col_map = {c.key: c.header for c in QUOTE_TABLE_COLUMNS}
        headers = [col_map[k] for k in self.visible_columns]
        for key in self.visible_tail_columns:
            headers.append(ALL_TAIL_COLUMNS.get(key, key))
        return headers

    def _all_quote_column_keys(self) -> list[str]:
        return [c.key for c in QUOTE_TABLE_COLUMNS]

    def column_settings_key(self) -> str:
        return f"quotes/columns/{self._p.page_name}"

    def save_column_config(self) -> None:
        page = self._p
        if not page.config.column_configurable:
            return
        settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
        settings.setValue(
            self.column_settings_key(),
            ",".join(self.visible_columns) + "|" + ",".join(self.visible_tail_columns),
        )

    def restore_column_config(self) -> None:
        page = self._p
        if not page.config.column_configurable:
            return
        settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
        value = settings.value(self.column_settings_key())
        if not isinstance(value, str):
            return
        parts = value.split("|", 1)
        if parts[0]:
            saved_cols = [k for k in parts[0].split(",") if k]
            all_keys = {c.key for c in QUOTE_TABLE_COLUMNS}
            valid_cols = [k for k in saved_cols if k in all_keys and k != "index"]
            for required in ("symbol", "name"):
                if required in all_keys and required not in valid_cols:
                    valid_cols.insert(0, required)
            valid_cols.insert(0, "index")
            self.visible_columns = valid_cols
        if len(parts) > 1 and parts[1]:
            self.visible_tail_columns = [k for k in parts[1].split(",") if k in ALL_TAIL_COLUMNS]

    def apply_header_layout(self, *, column_count: int | None = None) -> None:
        page = self._p
        view = self._view()
        header = view.horizontalHeader()
        header.setStretchLastSection(False)
        if page.config.use_local_table:
            for idx, mode in enumerate(
                [
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                    QtWidgets.QHeaderView.ResizeMode.Stretch,
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
                ]
            ):
                if idx < self._model().column_count():
                    header.setSectionResizeMode(idx, mode)
            return
        count = column_count if column_count is not None else self._model().column_count()
        for col in range(count):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        if "name" in self.visible_columns:
            name_idx = self.visible_columns.index("name")
            header.setSectionResizeMode(name_idx, QtWidgets.QHeaderView.ResizeMode.Stretch)

    def apply_filter(self) -> None:
        page = self._p
        if not page._active:
            return

        if page.config.use_market_rank:
            page._market_page = 0
            page.load_market_page()
            return

        keyword = page.search_edit.text().strip().lower()

        if page.config.require_keyword and not keyword:
            page.display_stocks = []
            self._model().set_row_count(0)
            page._quote_timer.stop()
            page.status_label.setText(f"共 {len(page.all_stocks)} 只 A 股，请输入关键词搜索（最多 {MAX_DISPLAY_ROWS} 条）")
            return

        matched = [s for s in page.all_stocks if keyword in s.search_key] if keyword else list(page.all_stocks)
        page.display_stocks = matched[:MAX_DISPLAY_ROWS]
        self.render_table()
        if page.config.auto_refresh_quotes:
            page.refresh_quotes()
            page._quote_timer.start()
        else:
            page._quote_timer.stop()

        extra = f"，显示前 {MAX_DISPLAY_ROWS} 条" if len(matched) > MAX_DISPLAY_ROWS else ""
        if not matched and page.config.scope_key == "自选池":
            page.status_label.setText("自选池为空，请在市场页搜索标的并点击「加入自选」")
        elif not matched and page.config.use_local_table:
            label = page._local_scope_label()
            page.status_label.setText(f"暂无本地{label}，请在自选页下载")
        elif page.config.use_local_table:
            stale = sum(
                1
                for item in matched
                if page.bar_list_status.get(
                    (item.symbol, item.exchange),
                    BarHealthStatus.UNKNOWN,
                )
                in (BarHealthStatus.STALE, BarHealthStatus.GAPS)
            )
            status = f"{page.page_name}  共 {len(matched)} 只{extra}"
            if stale:
                status += f"，{stale} 只需补全"
            page.status_label.setText(status)
            page._local.update_batch_toolbar_buttons()
        else:
            page.status_label.setText(f"{page.page_name}  匹配 {len(matched)} 只{extra}")

    def invalidate_symbol_row_index(self) -> None:
        self._symbol_row_index = None

    def _build_symbol_row_index(self) -> dict[str, int]:
        page = self._p
        symbol_rows: dict[str, int] = {}
        for row in range(self._model().row_count()):
            item = self.stock_at_row(row)
            if item is not None:
                symbol_rows[item.tickflow_symbol] = row
        self._symbol_row_index = symbol_rows
        return symbol_rows

    def schedule_stats_update(self) -> None:
        """WebSocket 高频推送时合并涨跌统计刷新。"""
        if self._p.stats_label is None:
            return
        self._stats_timer.start()

    def stock_at_row(self, row: int) -> StockItem | None:
        page = self._p
        if row < 0:
            return None
        item = self._model().stock_at_row(row)
        if item is not None:
            return item
        if row < len(page.display_stocks):
            return page.display_stocks[row]
        return None

    def selected_stock_key(self) -> tuple[str, Exchange] | None:
        if self._p.current_item is None:
            return None
        item = self._p.current_item
        return (item.symbol, item.exchange)

    def select_stock_key(self, key: tuple[str, Exchange]) -> None:
        view = self._view()
        for row in range(self._model().row_count()):
            item = self.stock_at_row(row)
            if item and (item.symbol, item.exchange) == key:
                view.selectRow(row)
                return

    def render_table(self, *, preserve_selection: bool = True) -> None:
        page = self._p
        self.invalidate_symbol_row_index()
        selected_key = self.selected_stock_key() if preserve_selection else None
        model = self._model()
        view = self._view()

        view.blockSignals(True)
        sorting_enabled = view.isSortingEnabled()
        view.setSortingEnabled(False)
        try:
            model.set_row_count(len(page.display_stocks))
            for row, item in enumerate(page.display_stocks):
                quote = page.quote_map.get(item.tickflow_symbol)
                self.set_row(row, item, quote)

            if selected_key:
                self.select_stock_key(selected_key)
            if view.currentIndex().row() < 0 and page.display_stocks:
                view.selectRow(0)
        finally:
            view.blockSignals(False)

        if page.config.table_header_sortable:
            view.setSortingEnabled(True)
            if page._apply_default_table_sort:
                page._apply_default_table_sort = False
                symbol_col = quote_column_index("symbol")
                view.sortByColumn(symbol_col, QtCore.Qt.SortOrder.AscendingOrder)
        elif sorting_enabled:
            view.setSortingEnabled(False)

        if view.currentIndex().row() >= 0:
            self.on_selection_changed()
        page._sync_stream_subscriptions()
        self._build_symbol_row_index()
        self.update_stats()

    def update_stats(self) -> None:
        page = self._p
        if page.stats_label is None:
            return
        total = len(page.display_stocks)
        up_count = 0
        down_count = 0
        flat_count = 0
        up_total_pct = 0.0
        for item in page.display_stocks:
            quote = page.quote_map.get(item.tickflow_symbol)
            if quote is None or not quote.last_price:
                flat_count += 1
                continue
            if quote.is_rise:
                up_count += 1
                up_total_pct += quote.change_pct
            elif quote.is_fall:
                down_count += 1
            else:
                flat_count += 1
        avg_pct = (up_total_pct / up_count) if up_count > 0 else 0.0
        colors = market_colors(theme_manager().tokens())
        parts = [f"自选池 {total} 只"]
        if up_count:
            parts.append(f'<span style="color:{colors.rise}">涨 {up_count}</span>')
        if down_count:
            parts.append(f'<span style="color:{colors.fall}">跌 {down_count}</span>')
        if flat_count:
            parts.append(f"平 {flat_count}")
        if up_count:
            parts.append(f" | 均涨幅 {avg_pct:+.2f}%")
        page.stats_label.setText("  |  ".join(parts))

    def refresh_table_quotes(self) -> None:
        page = self._p
        symbols = {item.tickflow_symbol for item in page.display_stocks}
        self.refresh_table_quotes_for_symbols(symbols)

    def refresh_table_quotes_for_symbols(self, symbols: set[str]) -> None:
        if not symbols:
            return
        page = self._p
        view = self._view()
        symbol_rows = self._symbol_row_index
        if symbol_rows is None:
            symbol_rows = self._build_symbol_row_index()

        sorting_enabled = view.isSortingEnabled()
        if sorting_enabled:
            view.setSortingEnabled(False)
        view.setUpdatesEnabled(False)
        view.blockSignals(True)
        try:
            for tf_symbol in symbols:
                row = symbol_rows.get(tf_symbol)
                if row is None:
                    continue
                item = self.stock_at_row(row)
                if item is None:
                    continue
                quote = page.quote_map.get(tf_symbol)
                self.set_row(row, item, quote)
        finally:
            view.blockSignals(False)
            view.setUpdatesEnabled(True)
        if sorting_enabled:
            view.setSortingEnabled(True)
            self.invalidate_symbol_row_index()
        self.schedule_stats_update()

    def refresh_row_for_item(self, item: StockItem) -> None:
        page = self._p
        for row in range(self._model().row_count()):
            row_item = self.stock_at_row(row)
            if row_item is None:
                continue
            if (row_item.symbol, row_item.exchange) != (item.symbol, item.exchange):
                continue
            quote = page.quote_map.get(item.tickflow_symbol)
            self.set_row(row, item, quote)
            break

    def display_index(self, row: int) -> int:
        page = self._p
        if page.config.use_market_rank:
            return page._market_page * page.config.market_page_size + row + 1
        return row + 1

    def _status_color(self, status: BarHealthStatus) -> str:
        if status == BarHealthStatus.OK:
            return STATUS_OK_COLOR
        if status == BarHealthStatus.STALE:
            return STATUS_STALE_COLOR
        if status == BarHealthStatus.GAPS:
            return STATUS_GAP_COLOR
        return market_colors(theme_manager().tokens()).flat

    def _local_tail_values(self, item: StockItem) -> list[str]:
        page = self._p
        key = (item.symbol, item.exchange)
        meta = page.bar_meta.get(key)
        status = page.bar_list_status.get(key, list_status(meta))
        minute = not page._is_daily_local_scope()
        return [
            format_meta_datetime(meta.start if meta else None, minute=minute),
            format_meta_datetime(meta.end if meta else None, minute=minute),
            str(meta.count) if meta else "—",
            status_label(status),
        ]

    def _quote_sort_key(
        self,
        column_key: str,
        item: StockItem,
        quote: QuoteSnapshot | None,
        index_text: str,
    ) -> float | str:
        if column_key == "index":
            return int(index_text)
        if column_key == "symbol":
            return item.symbol
        if column_key == "exchange":
            return item.exchange.value
        if column_key == "name":
            return (quote.name if quote and quote.name else item.name).lower()
        if quote is None:
            return float("-inf")
        numeric_map = {
            "last_price": quote.last_price,
            "change_pct": quote.change_pct,
            "change_amount": quote.change_amount,
            "amplitude": quote.amplitude,
            "turnover_rate": quote.turnover_rate,
            "volume": quote.volume,
            "amount": quote.amount,
            "high_price": quote.high_price,
            "low_price": quote.low_price,
            "open_price": quote.open_price,
            "prev_close": quote.prev_close,
        }
        if column_key in numeric_map:
            return numeric_map[column_key]
        if column_key == "trade_time":
            return quote.trade_time or ""
        return ""

    def _apply_table_cell(
        self,
        row: int,
        col: int,
        text: str,
        *,
        item: StockItem | None = None,
        sort_key: float | str | None = None,
        color: str | None = None,
    ) -> None:
        page = self._p
        self._model().apply_cell(
            row,
            col,
            text,
            sort_key=sort_key if page.config.table_header_sortable else None,
            color=color,
            stock_item=item,
        )

    def _set_local_row(self, row: int, item: StockItem) -> None:
        page = self._p
        key = (item.symbol, item.exchange)
        meta = page.bar_meta.get(key)
        status = page.bar_list_status.get(key, list_status(meta))
        minute = not page._is_daily_local_scope()
        values = build_local_data_row(
            item,
            str(self.display_index(row)),
            start=format_meta_datetime(meta.start if meta else None, minute=minute),
            end=format_meta_datetime(meta.end if meta else None, minute=minute),
            count=str(meta.count) if meta else "—",
            status=status_label(status),
        )
        status_col = len(values) - 1
        for col, text in enumerate(values):
            cell_color = self._status_color(status) if col == status_col else None
            self._apply_table_cell(row, col, text, item=item if col == 0 else None, color=cell_color)

    def set_row(self, row: int, item: StockItem, quote: QuoteSnapshot | None) -> None:
        page = self._p
        if page.config.use_local_table:
            self._set_local_row(row, item)
            return

        index_text = str(self.display_index(row))
        key = (item.symbol, item.exchange)
        if page.config.show_local_column:
            tail_value = "✓" if key in page.downloaded_keys else "—"
            tail_values = None
        elif page.config.show_fill_button and not page.config.use_local_table:
            tail_value = ""
            tail_values = self._local_tail_values(item)
        else:
            meta = page.bar_meta.get(key)
            count = meta.count if meta else 0
            tail_value = str(count) if count else "—"
            tail_values = None

        values, price_cols = build_quote_row(
            item,
            quote,
            index_text,
            tail_value,
            tail_values=tail_values,
        )
        all_keys = self._all_quote_column_keys()
        visible_indices: list[int] = []
        tail_start = len(all_keys)
        for col_key in self.visible_columns:
            if col_key in all_keys:
                visible_indices.append(all_keys.index(col_key))
        for _ in self.visible_tail_columns:
            visible_indices.append(tail_start)
            tail_start += 1

        filtered_values: list[str] = []
        filtered_price_cols: set[int] = set()
        filtered_sort_keys: list[float | str] = []
        for new_col, src_idx in enumerate(visible_indices):
            if src_idx < len(values):
                filtered_values.append(values[src_idx])
            else:
                filtered_values.append("—")
            if src_idx in price_cols:
                filtered_price_cols.add(new_col)
            if src_idx < len(all_keys):
                col_key = all_keys[src_idx]
                filtered_sort_keys.append(self._quote_sort_key(col_key, item, quote, index_text))
            else:
                filtered_sort_keys.append(values[src_idx] if src_idx < len(values) else "")

        tokens = theme_manager().tokens()
        colors = market_colors(tokens)
        color = colors.flat
        if quote:
            color = quote_change_color(quote, tokens)

        status_col: int | None = None
        status: BarHealthStatus | None = None
        if tail_values is not None:
            status_col = len(filtered_values) - 1
            status = page.bar_list_status.get(key, list_status(page.bar_meta.get(key)))

        for col, text in enumerate(filtered_values):
            cell_color = None
            if quote and col in filtered_price_cols:
                cell_color = color
            if status_col is not None and col == status_col and status is not None:
                cell_color = self._status_color(status)
            sort_key = filtered_sort_keys[col] if col < len(filtered_sort_keys) else text
            self._apply_table_cell(
                row,
                col,
                text,
                item=item if col == 0 else None,
                sort_key=sort_key,
                color=cell_color,
            )

    def on_selection_changed(self) -> None:
        page = self._p
        rows = self._view().selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        item = self.stock_at_row(idx)
        if item is None:
            return

        new_key = (item.symbol, item.exchange)
        old_key = self.selected_stock_key()
        page.current_item = item
        page._update_action_buttons()
        page._update_quote_header(item)
        if new_key != old_key:
            page._selected_gap_result = None
            if page.config.show_kline:
                page.show_kline(item)
            if page.config.show_fill_button and page._is_daily_local_scope():
                page._check_bar_gaps(item)
            if page.config.show_depth_panel:
                page.refresh_depth()
        page._sync_stream_depth_subscription()
        page._emit_ai_context()

    def show_column_menu(self) -> None:
        page = self._p
        menu = QtWidgets.QMenu(page)
        col_map = {c.key: c.header for c in QUOTE_TABLE_COLUMNS}

        for key in [c.key for c in QUOTE_TABLE_COLUMNS]:
            if key == "index":
                continue
            action = menu.addAction(col_map.get(key, key))
            action.setCheckable(True)
            action.setChecked(key in self.visible_columns)
            action.setData(key)
            action.triggered.connect(lambda checked, k=key: self.on_column_toggle(k, checked))

        menu.addSeparator()

        for key, header in ALL_TAIL_COLUMNS.items():
            action = menu.addAction(header)
            action.setCheckable(True)
            action.setChecked(key in self.visible_tail_columns)
            action.setData(key)
            action.triggered.connect(lambda checked, k=key: self.on_tail_column_toggle(k, checked))

        button = page.column_button
        menu.popup(button.mapToGlobal(button.rect().bottomLeft()))

    def on_column_toggle(self, key: str, checked: bool) -> None:
        if checked and key not in self.visible_columns:
            self.visible_columns.append(key)
        elif not checked and key in self.visible_columns:
            self.visible_columns.remove(key)
        self.rebuild_table()

    def on_tail_column_toggle(self, key: str, checked: bool) -> None:
        if checked and key not in self.visible_tail_columns:
            self.visible_tail_columns.append(key)
        elif not checked and key in self.visible_tail_columns:
            self.visible_tail_columns.remove(key)
        self.rebuild_table()

    def rebuild_table(self) -> None:
        headers = self.build_visible_headers()
        self._model().set_headers(headers)
        self.apply_header_layout(column_count=len(headers))
        self.render_table()
