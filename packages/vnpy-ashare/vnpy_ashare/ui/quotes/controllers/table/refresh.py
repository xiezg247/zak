"""表格行情增量刷新与涨跌统计。"""

from __future__ import annotations

from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.ui.quotes.controllers.table.base import TableControllerBase
from vnpy_ashare.ui.quotes.page.config import MARKET_SCROLL_REFRESH_VISIBLE_BUFFER
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import market_colors


class TableRefreshMixin(TableControllerBase):
    def schedule_stats_update(self) -> None:
        """WebSocket 高频推送时合并涨跌统计刷新。"""
        if self._p._stats_label is None:
            return
        self._stats_timer.start()

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
        groups = getattr(page, "_watchlist_groups", None)
        if groups is not None and groups.is_filtering():
            parts[0] = f"分组「{groups.active_group_label()}」 {total} 只"
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
        if page.config.show_watchlist_positions:
            page._positions.refresh_quotes_only(symbols)
        if page.config.show_watchlist_multiview:
            page._multiview.on_quotes_updated()

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
