"""表格行渲染与增量追加。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

from vnpy_ashare.data.bar_health import (
    BarHealthStatus,
    format_meta_datetime,
    list_status,
    status_label,
)
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.quotes.rank.rank_engine import quote_rank_value
from vnpy_ashare.ui.quotes.controllers.table.base import TableControllerBase
from vnpy_ashare.ui.quotes.table.columns import (
    build_local_data_row,
    build_quote_row,
    quote_column_index,
)
from vnpy_ashare.ui.quotes.table.model import QuoteCell
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import MarketColors, market_colors
from vnpy_common.ui.theme.tokens import ThemeTokens


class TableRenderMixin(TableControllerBase):
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
            industry = self._market_industry_map(self._p).get(item.ts_code, "")
            return str(industry).lower()
        if column_key == "market_board":
            board = self._market_board_map(self._p).get(item.ts_code, "")
            return str(board).lower()
        if quote is None:
            return float("-inf")

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
