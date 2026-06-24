"""全市场列表筛选、排序与状态文案。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.market.board import matches_board
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.domain.time.quote_time import format_batch_updated_at
from vnpy_ashare.services.industry_sector import fetch_stock_industry_map, fetch_stock_market_board_map
from vnpy_ashare.ui.quotes.controllers.table.base import TableControllerBase
from vnpy_ashare.ui.quotes.table.display import slice_market_display, sort_market_items

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class TableMarketMixin(TableControllerBase):
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

        page._industry_map_cache = fetch_stock_industry_map()
        return page._industry_map_cache

    @staticmethod
    def _market_board_map(page: QuotesPage) -> dict[str, str]:
        cached = page._market_board_map_cache
        if cached is not None:
            return cached

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

        vt_whitelist = page._market_vt_whitelist
        if vt_whitelist:
            matched = [item for item in matched if item.vt_symbol in vt_whitelist]

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
            page=page._market_page,
            page_size=page.config.market_page_size,
        )

        page._apply_default_table_sort = False
        self.render_table()
        if page.market_auto_refresh_enabled():
            page.schedule_quote_auto_refresh()
        else:
            page._quote_timer.stop()

        page.status_label.setText(self._format_market_status(len(sorted_items)))
        page._update_quote_source_label()
        page._pagination.set_visible()
        page._pagination.update_controls()

    def on_market_header_clicked(self, section: int) -> None:
        page = self._p
        if page.config.market_full_list and not page._market_catalog_loaded:
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
        drilldown = page._market_drilldown_label
        catalog_count = len(page._market_catalog)
        batch_time = format_batch_updated_at(page._market_updated_at)
        rank_title = page.active_rank_title() if page.config.show_rank_sidebar else None

        page_size = max(page.config.market_page_size, 1)
        page_count = max((matched_count + page_size - 1) // page_size, 1)
        current = min(page._market_page + 1, page_count)
        if keyword or board or industry or drilldown:
            status = f"筛选 {matched_count} 只，排序后第 {current}/{page_count} 页（全市场 {catalog_count} 只）"
            if drilldown:
                status = f"{drilldown} · {status}"
        elif rank_title:
            status = f"{rank_title} {matched_count} 只，第 {current}/{page_count} 页"
        else:
            status = f"全市场 {matched_count} 只，排序后第 {current}/{page_count} 页"

        if batch_time:
            status += f"，行情更新于 {batch_time}"
        elif catalog_count == 0:
            status += "（Redis 暂无行情，请运行 quote_collector）"
        return status
