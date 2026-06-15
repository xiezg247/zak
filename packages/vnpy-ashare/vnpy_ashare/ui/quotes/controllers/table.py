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
from vnpy_ashare.domain.board import matches_board
from vnpy_ashare.domain.market_hours import is_ashare_trading_session
from vnpy_ashare.domain.quote_time import format_batch_updated_at
from vnpy_ashare.domain.signal_snapshot import SIGNAL_COLUMN_KEYS
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.ui.quotes.page.config import (
    ALL_TAIL_COLUMNS,
    DEFAULT_WATCHLIST_COLUMNS,
    MARKET_SCROLL_REFRESH_VISIBLE_BUFFER,
    MARKET_VISIBLE_COLUMNS,
    MAX_DISPLAY_ROWS,
    STATS_DEBOUNCE_MS,
)
from vnpy_ashare.ui.quotes.table import QuoteTableModel
from vnpy_ashare.ui.quotes.table.columns import (
    QUOTE_TABLE_COLUMNS,
    build_local_data_row,
    build_quote_row,
    quote_column_index,
)
from vnpy_ashare.ui.quotes.table.display import slice_market_display, sort_market_items
from vnpy_ashare.ui.quotes.table.model import QuoteCell
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import MarketColors, market_colors
from vnpy_common.ui.theme.tokens import ThemeTokens

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


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

    def _model(self) -> QuoteTableModel:
        return self._p.quote_table_model

    def _view(self) -> QtWidgets.QTableView:
        return self._p.market_table

    def _signal_column_keys(self) -> frozenset[str]:
        return SIGNAL_COLUMN_KEYS

    def _strip_signal_columns(self, keys: list[str]) -> list[str]:
        blocked = self._signal_column_keys()
        return [key for key in keys if key not in blocked]

    def _default_main_columns(self) -> list[str]:
        page = self._p
        all_keys = [c.key for c in QUOTE_TABLE_COLUMNS]
        if page.page_name == "自选":
            default_main = [k for k in DEFAULT_WATCHLIST_COLUMNS if k in all_keys]
        else:
            default_main = [k for k in MARKET_VISIBLE_COLUMNS if k in all_keys]
        default_main = self._strip_signal_columns(default_main)
        for required in ("index", "symbol", "name"):
            if required in all_keys and required not in default_main:
                default_main.insert(0, required)
        return default_main

    def init_columns(self) -> None:
        self.visible_columns = self._default_main_columns()
        self.visible_tail_columns = self._default_tail_columns()
        self.restore_column_config()
        self.sync_tail_columns_with_config()

    def _allowed_tail_column_keys(self) -> set[str]:
        page = self._p
        if page.config.use_local_table:
            return set()
        allowed: set[str] = set()
        if page.config.show_local_column:
            allowed.add("local")
        if page.config.show_fill_button and not page.config.use_local_table:
            allowed.update(("start", "end", "count", "status"))
        return allowed

    def _sanitize_tail_columns(self) -> bool:
        allowed = self._allowed_tail_column_keys()
        sanitized = [key for key in self.visible_tail_columns if key in allowed]
        if sanitized == self.visible_tail_columns:
            return False
        self.visible_tail_columns = sanitized
        return True

    def sync_tail_columns_with_config(self) -> bool:
        """按页面配置剔除无效尾列；有变更时写回 QSettings 并提示需重建表头。"""
        if not self._sanitize_tail_columns():
            return False
        self.save_column_config()
        return True

    def _default_tail_columns(self) -> list[str]:
        page = self._p
        if page.config.use_local_table:
            return []
        if page.config.show_fill_button and not page.config.use_local_table:
            return ["start", "end", "count", "status"]
        if page.config.show_local_column:
            return ["local"]
        return []

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
            valid_cols = self._strip_signal_columns(valid_cols)
            for required in ("symbol", "name"):
                if required in all_keys and required not in valid_cols:
                    valid_cols.insert(0, required)
            valid_cols.insert(0, "index")
            if page.page_name == "市场":
                insert_at = valid_cols.index("name") + 1 if "name" in valid_cols else 1
                for key in ("industry", "market_board"):
                    if key in all_keys and key not in valid_cols:
                        valid_cols.insert(insert_at, key)
                        insert_at += 1
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
            if page.market_auto_refresh_enabled():
                page._market_page = 0
                page._market_page_cache.clear()
                page._pagination.set_visible()
                if page.market_uses_client_pagination():
                    self.filter_market_display()
                else:
                    page.load_market_page()
                return
            if page.config.market_full_list:
                page._pagination.set_visible(False)
                if page._market_catalog_loaded:
                    self.filter_market_display()
                else:
                    page.load_market_full()
                return
            page._market_page = 0
            page._market_page_cache.clear()
            page._market_loading_more = False
            page._market_last_load_more_at = 0.0
            page.load_market_page()
            return

        keyword = page.search_edit.text().strip().lower()

        if page.config.use_local_pagination:
            matched = [s for s in page.all_stocks if keyword in s.search_key] if keyword else list(page.all_stocks)
            display_unchanged = self._same_stock_list(page.display_stocks, matched)
            page.display_stocks = matched
            table_rows = self._model().row_count()
            if not display_unchanged or table_rows != len(matched):
                self.render_table()
            page._pagination.update_controls()
            if page._local_total == 0:
                label = page._local_scope_label()
                page.status_label.setText(f"暂无本地{label}，请在自选页下载")
            else:
                stale = sum(
                    1
                    for item in matched
                    if page.bar_list_status.get(
                        (item.symbol, item.exchange),
                        BarHealthStatus.UNKNOWN,
                    )
                    in (BarHealthStatus.STALE, BarHealthStatus.GAPS)
                )
                status = page._pagination.format_local_status()
                if keyword:
                    status += "（当前页筛选）"
                if stale:
                    status += f"，本页 {stale} 只需补全"
                page.status_label.setText(status)
            page._local.update_batch_toolbar_buttons()
            return

        if page.config.require_keyword and not keyword:
            page.display_stocks = []
            self._model().set_row_count(0)
            page._quote_timer.stop()
            page.status_label.setText(f"共 {len(page.all_stocks)} 只 A 股，请输入关键词搜索（最多 {MAX_DISPLAY_ROWS} 条）")
            return

        matched = [s for s in page.all_stocks if keyword in s.search_key] if keyword else list(page.all_stocks)
        next_display = matched[:MAX_DISPLAY_ROWS]
        display_unchanged = self._same_stock_list(page.display_stocks, next_display)
        page.display_stocks = next_display
        table_rows = self._model().row_count()
        if not display_unchanged or table_rows != len(next_display) or page.config.use_local_table:
            self.render_table()
        if page.config.show_watchlist_signals:
            page._signals.start()
        if page.config.auto_refresh_quotes:
            if is_ashare_trading_session():
                page.refresh_quotes()
            page.schedule_quote_auto_refresh()
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

    def _market_board_base_items(self, page: QuotesPage) -> list[StockItem]:
        board_key = page._market_board or ""
        if page._market_board_base is not None and page._market_board_base_key == board_key:
            return page._market_board_base
        base = [item for item in page._market_catalog if matches_board(item.symbol, page._market_board)]
        page._market_board_base = base
        page._market_board_base_key = board_key
        return base

    @staticmethod
    def _market_industry_map(page: QuotesPage) -> dict[str, str]:
        cached = page._industry_map_cache
        if cached is not None:
            return cached
        from vnpy_ashare.integrations.tushare.factors import fetch_stock_industry_map

        page._industry_map_cache = fetch_stock_industry_map()
        return page._industry_map_cache

    @staticmethod
    def _market_board_map(page: QuotesPage) -> dict[str, str]:
        cached = page._market_board_map_cache
        if cached is not None:
            return cached
        from vnpy_ashare.integrations.tushare.factors import fetch_stock_market_board_map

        page._market_board_map_cache = fetch_stock_market_board_map()
        return page._market_board_map_cache

    @staticmethod
    def _same_stock_list(left: list[StockItem], right: list[StockItem]) -> bool:
        if len(left) != len(right):
            return False
        for left_item, right_item in zip(left, right, strict=True):
            if (left_item.symbol, left_item.exchange) != (right_item.symbol, right_item.exchange):
                return False
        return True

    def filter_market_display(self) -> None:
        """全量市场列表：内存筛选板块与关键词。"""
        page = self._p
        keyword = page.search_edit.text().strip().lower()
        prev_keyword = page._market_filter_keyword
        base = self._market_board_base_items(page)

        if not keyword:
            matched = base
        elif prev_keyword and keyword.startswith(prev_keyword) and page._market_matched:
            matched = [item for item in page._market_matched if keyword in item.search_key]
        else:
            matched = [item for item in base if keyword in item.search_key]

        industry_filter = page._market_industry_filter
        if industry_filter:
            industry_map = self._market_industry_map(page)
            matched = [item for item in matched if industry_map.get(item.ts_code, "") == industry_filter]

        page._market_filter_keyword = keyword
        if self._same_stock_list(matched, page._market_matched):
            return

        page._market_matched = matched
        self.apply_market_display()

    def apply_market_display(self) -> None:
        """对筛选结果全量排序，再按模式切片展示。"""
        page = self._p
        sorted_items = self._sort_market_items(page._market_matched)
        page._market_total = len(sorted_items)
        page.display_stocks = slice_market_display(
            sorted_items,
            live_mode=page.market_auto_refresh_enabled(),
            page=page._market_page,
            page_size=page.config.market_page_size,
            live_display_limit=page.config.market_live_display_limit,
        )

        page._apply_default_table_sort = False
        self.render_table()
        if page.market_auto_refresh_enabled():
            page.schedule_quote_auto_refresh()
        else:
            page._quote_timer.stop()

        page.status_label.setText(self._format_market_status(len(sorted_items)))
        page._update_quote_source_label()
        if page.market_auto_refresh_enabled():
            page._pagination.set_visible()
            page._pagination.update_controls()
        else:
            page._pagination.set_visible(False)
            page._pagination.update_controls()

    def on_market_header_clicked(self, section: int) -> None:
        page = self._p
        if page.market_auto_refresh_enabled() and not page._market_catalog_loaded:
            if section < 0 or section >= len(self.visible_columns):
                return
            col_key = self.visible_columns[section]
            if page._market_sort_column == col_key:
                page._market_sort_ascending = not page._market_sort_ascending
            else:
                page._market_sort_column = col_key
                page._market_sort_ascending = True
            page._market_page = 0
            page.load_market_full(quiet=False)
            return
        if section < 0 or section >= len(self.visible_columns):
            return
        col_key = self.visible_columns[section]
        if page._market_sort_column == col_key:
            page._market_sort_ascending = not page._market_sort_ascending
        else:
            page._market_sort_column = col_key
            page._market_sort_ascending = True
        page._market_page = 0
        self._sync_market_sort_indicator()
        self.apply_market_display()

    def _sync_market_sort_indicator(self) -> None:
        page = self._p
        col_key = page._market_sort_column
        if not col_key or col_key not in self.visible_columns:
            return
        section = self.visible_columns.index(col_key)
        order = QtCore.Qt.SortOrder.AscendingOrder if page._market_sort_ascending else QtCore.Qt.SortOrder.DescendingOrder
        self._view().horizontalHeader().setSortIndicator(section, order)

    def _sort_market_items(self, items: list[StockItem]) -> list[StockItem]:
        page = self._p
        return sort_market_items(
            items,
            sort_column=page._market_sort_column,
            ascending=page._market_sort_ascending,
            catalog=page._market_catalog,
            quote_map=page.quote_map,
            sort_key_fn=self._quote_sort_key,
        )

    def _format_market_status(self, matched_count: int) -> str:
        page = self._p
        keyword = page.search_edit.text().strip()
        board = page._market_board
        industry = page._market_industry_filter
        catalog_count = len(page._market_catalog)
        batch_time = format_batch_updated_at(page._market_updated_at)
        rank_title = page.active_rank_title() if page.config.show_rank_sidebar else None

        if page.market_auto_refresh_enabled():
            page_size = max(page.config.market_page_size, 1)
            page_count = max((matched_count + page_size - 1) // page_size, 1)
            current = min(page._market_page + 1, page_count)
            if keyword or board or industry:
                status = f"筛选 {matched_count} 只，排序后第 {current}/{page_count} 页（全市场 {catalog_count} 只）"
            elif rank_title:
                status = f"{rank_title} {matched_count} 只，第 {current}/{page_count} 页"
            else:
                status = f"全市场 {matched_count} 只，排序后第 {current}/{page_count} 页"
        elif keyword or board or industry:
            status = f"筛选 {matched_count} 只（全市场 {catalog_count} 只）"
        elif rank_title:
            status = f"{rank_title} 共 {catalog_count} 只"
        else:
            status = f"共 {catalog_count} 只"

        if batch_time:
            status += f"，行情更新于 {batch_time}"
        elif catalog_count == 0:
            status += "（Redis 暂无行情，请运行 quote_collector）"
        return status

    def invalidate_symbol_row_index(self) -> None:
        self._symbol_row_index = None

    def _build_symbol_row_index(self) -> dict[str, int]:
        symbol_rows: dict[str, int] = {}
        for row in range(self._model().row_count()):
            item = self.stock_at_row(row)
            if item is not None:
                symbol_rows[item.tickflow_symbol] = row
        self._symbol_row_index = symbol_rows
        return symbol_rows

    def _extend_symbol_row_index(self, start_row: int, items: list[StockItem]) -> None:
        if self._symbol_row_index is None:
            self._build_symbol_row_index()
            return
        for offset, item in enumerate(items):
            self._symbol_row_index[item.tickflow_symbol] = start_row + offset

    def schedule_stats_update(self) -> None:
        """WebSocket 高频推送时合并涨跌统计刷新。"""
        if self._p._stats_label is None:
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

    def selected_items(self) -> list[StockItem]:
        rows = self._view().selectionModel().selectedRows()
        items: list[StockItem] = []
        for model_index in rows:
            item = self.stock_at_row(model_index.row())
            if item is not None:
                items.append(item)
        return items

    def select_stock_key(self, key: tuple[str, Exchange]) -> None:
        view = self._view()
        for row in range(self._model().row_count()):
            item = self.stock_at_row(row)
            if item and (item.symbol, item.exchange) == key:
                view.selectRow(row)
                view.scrollTo(view.model().index(row, 0), QtWidgets.QAbstractItemView.ScrollHint.EnsureVisible)
                return

    def focus_market_symbol(self, vt_symbol: str) -> bool:
        """清除筛选并翻页定位到主表中的标的。"""
        from vnpy_ashare.domain.symbols import parse_stock_symbol

        page = self._p
        if not page.config.use_market_rank or not page.config.market_full_list:
            return False
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            return False
        target_key = (item.symbol, item.exchange)

        page.search_edit.blockSignals(True)
        page.search_edit.clear()
        page.search_edit.blockSignals(False)
        if page.config.show_board_filter and page._market_board is not None:
            page.board_combo.blockSignals(True)
            page.board_combo.setCurrentIndex(0)
            page.board_combo.blockSignals(False)
            page._market_board = None
            page._market_board_base = None
            page._market_board_base_key = None

        page._market_industry_filter = None
        listener = page._market_industry_filter_listener
        if listener is not None:
            listener(None)

        if not page._market_catalog:
            return False

        page._market_filter_keyword = ""
        sorted_items = self._sort_market_items(list(page._market_catalog))
        index = next(
            (idx for idx, stock in enumerate(sorted_items) if (stock.symbol, stock.exchange) == target_key),
            None,
        )
        if index is None:
            return False

        page._market_matched = sorted_items
        page_size = max(page.config.market_page_size, 1)
        page._market_page = index // page_size
        self.apply_market_display()
        self.select_stock_key(target_key)
        return self._view().currentIndex().row() >= 0

    def render_table(self, *, preserve_selection: bool = True) -> None:
        page = self._p
        self.invalidate_symbol_row_index()
        selected_key = self.selected_stock_key() if preserve_selection else None
        model = self._model()
        view = self._view()

        view.blockSignals(True)
        view.setUpdatesEnabled(False)
        sorting_enabled = view.isSortingEnabled()
        view.setSortingEnabled(False)
        try:
            row_cells = [self._build_row_cells(row, item, page.quote_map.get(item.tickflow_symbol)) for row, item in enumerate(page.display_stocks)]
            model.set_rows(row_cells)

            if selected_key:
                self.select_stock_key(selected_key)
            if view.currentIndex().row() < 0 and page.display_stocks:
                view.selectRow(0)
        finally:
            view.setUpdatesEnabled(True)
            view.blockSignals(False)

        market_custom_sort = page.config.use_market_rank and page.config.market_full_list
        if page.config.table_header_sortable and not market_custom_sort:
            view.setSortingEnabled(True)
            if page._apply_default_table_sort:
                page._apply_default_table_sort = False
                symbol_col = quote_column_index("symbol")
                view.sortByColumn(symbol_col, QtCore.Qt.SortOrder.AscendingOrder)
        elif market_custom_sort:
            view.setSortingEnabled(False)
            self._sync_market_sort_indicator()
        elif sorting_enabled:
            view.setSortingEnabled(False)

        if view.currentIndex().row() >= 0:
            self.on_selection_changed()
        page._sync_stream_subscriptions()
        self._build_symbol_row_index()
        self.update_stats()
        self._refresh_market_scrollbar()

    def _refresh_market_scrollbar(self) -> None:
        page = self._p
        if not page.config.use_market_rank:
            return
        host = getattr(page, "_market_table_host", None)
        if host is not None:
            host.refresh_scrollbar()

    def append_rows(
        self,
        start_row: int,
        items: list[StockItem],
        quotes: dict[str, QuoteSnapshot],
    ) -> None:
        """下拉分页：在表格末尾追加一批行。"""
        if not items:
            return
        page = self._p
        view = self._view()
        bar = view.verticalScrollBar()
        scroll_value = bar.value()

        tokens = theme_manager().tokens()
        colors = market_colors(tokens)
        row_cells = [
            self._build_row_cells(
                start_row + offset,
                item,
                quotes.get(item.tickflow_symbol),
                colors=colors,
            )
            for offset, item in enumerate(items)
        ]

        page._market_scroll_blocked = True
        sorting_enabled = view.isSortingEnabled()
        bar.blockSignals(True)
        view.setUpdatesEnabled(False)
        view.setSortingEnabled(False)
        try:
            self._model().append_rows(row_cells)
            self._extend_symbol_row_index(start_row, items)
        finally:
            view.setSortingEnabled(sorting_enabled)
            view.setUpdatesEnabled(True)
            bar.blockSignals(False)
            bar.setValue(min(scroll_value, bar.maximum()))
            page._market_scroll_blocked = False
        self._refresh_market_scrollbar()

    def update_stats(self) -> None:
        page = self._p
        label = page._stats_label
        if label is None:
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
        label.setText("  |  ".join(parts))

    def visible_market_items(self) -> list[StockItem]:
        """市场页下拉模式：仅取视口内（含缓冲）标的，供增量行情刷新。"""
        view = self._view()
        row_count = self._model().row_count()
        if row_count <= 0:
            return []

        top = view.rowAt(0)
        if top < 0:
            top = 0
        bottom = view.rowAt(view.viewport().height() - 1)
        if bottom < 0:
            bottom = row_count - 1

        buffer = MARKET_SCROLL_REFRESH_VISIBLE_BUFFER
        start = max(0, top - buffer)
        end = min(row_count - 1, bottom + buffer)
        items: list[StockItem] = []
        for row in range(start, end + 1):
            item = self.stock_at_row(row)
            if item is not None:
                items.append(item)
        return items

    def refresh_visible_table_quotes(self) -> None:
        symbols = {item.tickflow_symbol for item in self.visible_market_items()}
        self.refresh_table_quotes_for_symbols(symbols)

    def refresh_table_quotes(self) -> None:
        page = self._p
        if page.config.market_scroll_paging:
            self.refresh_visible_table_quotes()
            return
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
        tokens = theme_manager().tokens()
        colors = market_colors(tokens)
        try:
            for tf_symbol in symbols:
                row = symbol_rows.get(tf_symbol)
                if row is None:
                    continue
                item = self.stock_at_row(row)
                if item is None:
                    continue
                quote = page.quote_map.get(tf_symbol)
                row_cells = self._build_row_cells(row, item, quote, colors=colors)
                self._model().apply_row(
                    row,
                    row_cells,
                    sortable=page.config.table_header_sortable,
                )
        finally:
            view.blockSignals(False)
            view.setUpdatesEnabled(True)
        if sorting_enabled:
            view.setSortingEnabled(True)
        self.schedule_stats_update()
        if page.config.show_watchlist_signals:
            page._signals.refresh_quotes_only(symbols)

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
        if page.config.use_market_rank and (page.market_auto_refresh_enabled() or not page.config.market_scroll_paging):
            return page._market_page * page.config.market_page_size + row + 1
        return row + 1

    def _status_color(
        self,
        status: BarHealthStatus,
        *,
        tokens: ThemeTokens | None = None,
    ) -> str:
        t = tokens or theme_manager().tokens()
        if status == BarHealthStatus.OK:
            return t.semantic_success
        if status == BarHealthStatus.STALE:
            return t.semantic_warning
        if status == BarHealthStatus.GAPS:
            return t.semantic_error
        return market_colors(t).flat

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
        if column_key == "industry":
            return self._market_industry_map(self._p).get(item.ts_code, "").lower()
        if column_key == "market_board":
            return self._market_board_map(self._p).get(item.ts_code, "").lower()
        if quote is None:
            return float("-inf")
        from vnpy_ashare.quotes.rank.rank_engine import quote_rank_value

        if column_key == "intraday_change_pct":
            return quote_rank_value(quote, column_key)
        numeric_map = {
            "last_price": quote.last_price,
            "change_pct": quote.change_pct,
            "limit_times": quote.limit_times,
            "change_speed_5m": quote.change_speed_5m,
            "change_amount": quote.change_amount,
            "amplitude": quote.amplitude,
            "turnover_rate": quote.turnover_rate,
            "volume_ratio": quote.volume_ratio,
            "net_mf_amount": quote.net_mf_amount,
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

    def _build_row_cells(
        self,
        row: int,
        item: StockItem,
        quote: QuoteSnapshot | None,
        *,
        colors: MarketColors | None = None,
        tokens: ThemeTokens | None = None,
    ) -> list[QuoteCell]:
        page = self._p
        if page.config.use_local_table:
            return self._build_local_row_cells(row, item)

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

        need_industry = "industry" in self.visible_columns or page._market_industry_filter
        need_board = "market_board" in self.visible_columns
        industry_map = self._market_industry_map(page) if need_industry else {}
        board_map = self._market_board_map(page) if need_board else {}
        industry = industry_map.get(item.ts_code, "")
        market_board = board_map.get(item.ts_code, "")

        values, price_cols = build_quote_row(
            item,
            quote,
            index_text,
            tail_value,
            tail_values=tail_values,
            industry=industry,
            market_board=market_board,
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
            if src_idx < len(all_keys):
                col_key = all_keys[src_idx]
            else:
                col_key = ""
            if src_idx < len(values):
                filtered_values.append(values[src_idx])
            else:
                filtered_values.append("—")
            if src_idx in price_cols:
                filtered_price_cols.add(new_col)
            if src_idx < len(all_keys):
                filtered_sort_keys.append(self._quote_sort_key(col_key, item, quote, index_text))
            else:
                filtered_sort_keys.append(values[src_idx] if src_idx < len(values) else "")

        if tokens is None:
            tokens = theme_manager().tokens()
        if colors is None:
            colors = market_colors(tokens)
        color = colors.flat
        if quote:
            if quote.is_rise:
                color = colors.rise
            elif quote.is_fall:
                color = colors.fall

        status_col: int | None = None
        status: BarHealthStatus | None = None
        if tail_values is not None:
            status_col = len(filtered_values) - 1
            status = page.bar_list_status.get(key, list_status(page.bar_meta.get(key)))

        cells: list[QuoteCell] = []
        sortable = page.config.table_header_sortable
        for col, text in enumerate(filtered_values):
            cell_color = None
            if quote and col in filtered_price_cols:
                cell_color = color
            if status_col is not None and col == status_col and status is not None:
                cell_color = self._status_color(status, tokens=tokens)
            sort_key = filtered_sort_keys[col] if col < len(filtered_sort_keys) else text
            cells.append(
                QuoteCell(
                    text=text,
                    sort_key=sort_key if sortable else "",
                    color=cell_color,
                    stock_item=item if col == 0 else None,
                )
            )
        return cells

    def _build_local_row_cells(self, row: int, item: StockItem) -> list[QuoteCell]:
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
        cells: list[QuoteCell] = []
        for col, text in enumerate(values):
            cell_color = self._status_color(status) if col == status_col else None
            cells.append(
                QuoteCell(
                    text=text,
                    color=cell_color,
                    stock_item=item if col == 0 else None,
                )
            )
        return cells

    def set_row(self, row: int, item: StockItem, quote: QuoteSnapshot | None) -> None:
        page = self._p
        if page.config.use_local_table:
            cells = self._build_local_row_cells(row, item)
        else:
            cells = self._build_row_cells(row, item, quote)
        self._model().apply_row(
            row,
            cells,
            sortable=page.config.table_header_sortable,
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
        if page.config.show_stock_notes:
            page._stock_notes.on_selection_item()
        if page.config.show_watchlist_signals:
            panel = getattr(page, "signal_panel", None)
            if panel is not None:
                if item.vt_symbol in panel.symbols:
                    panel.highlight_symbol(item.vt_symbol)
                else:
                    panel.highlight_symbol(None)
            if page.chart_panel is not None and page.current_item is not None:
                snap = page.signal_cache.get(page.current_item.vt_symbol)
                if snap is not None:
                    quote = page.quote_map.get(page.current_item.tickflow_symbol)
                    ref_kwargs = page._signal_chart_ref_kwargs()
                    page.chart_panel.apply_signal_reference(snap, quote=quote, **ref_kwargs)
        if page.config.show_watchlist_positions:
            position_panel = getattr(page, "position_panel", None)
            position_service = page._get_position_service()
            if position_panel is not None and position_service is not None:
                if position_service.contains(item.symbol, item.exchange):
                    position_panel.highlight_symbol(item.vt_symbol)

    def show_column_menu(self) -> None:
        page = self._p
        menu = QtWidgets.QMenu(page)
        col_map = {c.key: c.header for c in QUOTE_TABLE_COLUMNS}

        for key in [c.key for c in QUOTE_TABLE_COLUMNS]:
            if key == "index":
                continue
            if key in self._signal_column_keys():
                continue
            action = menu.addAction(col_map.get(key, key))
            action.setCheckable(True)
            action.setChecked(key in self.visible_columns)
            action.setData(key)
            action.triggered.connect(lambda checked, k=key: self.on_column_toggle(k, checked))

        allowed_tail = self._allowed_tail_column_keys()
        if allowed_tail:
            menu.addSeparator()
            for key, header in ALL_TAIL_COLUMNS.items():
                if key not in allowed_tail:
                    continue
                action = menu.addAction(header)
                action.setCheckable(True)
                action.setChecked(key in self.visible_tail_columns)
                action.setData(key)
                action.triggered.connect(lambda checked, k=key: self.on_tail_column_toggle(k, checked))

        button = page.column_button
        if button is None:
            return
        menu.popup(button.mapToGlobal(button.rect().bottomLeft()))

    def on_column_toggle(self, key: str, checked: bool) -> None:
        if checked and key not in self.visible_columns:
            self.visible_columns.append(key)
        elif not checked and key in self.visible_columns:
            self.visible_columns.remove(key)
        self.rebuild_table()

    def on_tail_column_toggle(self, key: str, checked: bool) -> None:
        if key not in self._allowed_tail_column_keys():
            return
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
