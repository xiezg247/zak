"""表格选中、翻页定位与选择变更回调。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.trading_universe import is_market_board_combo_locked
from vnpy_ashare.domain.symbols.stock import StockItem, parse_stock_symbol
from vnpy_ashare.ui.quotes.controllers.table.base import TableControllerBase


class TableSelectionMixin(TableControllerBase):
    def select_row(self, row: int, *, clear: bool = True) -> None:
        """选中整行；默认先清空旧选区，避免 Extended 模式下叠出多行异色。"""
        view = self._view()
        model = view.model()
        if row < 0 or row >= model.rowCount():
            return
        index = model.index(row, 0)
        flags = (
            QtCore.QItemSelectionModel.SelectionFlag.Select
            | QtCore.QItemSelectionModel.SelectionFlag.Rows
        )
        if clear:
            flags |= QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect
        view.selectionModel().select(index, flags)
        view.scrollTo(index, QtWidgets.QAbstractItemView.ScrollHint.EnsureVisible)

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
        for row in range(self._model().row_count()):
            item = self.stock_at_row(row)
            if item and (item.symbol, item.exchange) == key:
                self.select_row(row)
                return

    def focus_market_symbol(self, vt_symbol: str) -> bool:
        """清除筛选并翻页定位到主表中的标的。"""

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
        if page.config.show_board_filter and page._market_board is not None and not is_market_board_combo_locked():
            page.board_combo.blockSignals(True)
            page.board_combo.setCurrentIndex(0)
            page.board_combo.blockSignals(False)
            page._market_board = None
            page._market_board_base = None
            page._market_board_base_key = None

        page._market_industry_filter = None
        page._market_vt_whitelist = None
        page._market_drilldown_label = None
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
        if page.config.show_watchlist_multiview:
            page._multiview.on_table_selection_changed()
