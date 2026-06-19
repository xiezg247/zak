"""自选池 UI 控制器（委托 WatchlistService）。"""

from __future__ import annotations

from typing import Literal, cast

from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.config.runtime import format_vt_symbol_cn
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.services.watchlist import WATCHLIST_MAX_ITEMS, WatchlistService
from vnpy_ashare.ui.quotes.watchlist.bootstrap import WatchlistBootstrapCoordinator
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_ashare.ui.quotes.watchlist.pool_host import WatchlistPoolHost


class WatchlistController:
    """封装自选 CRUD 与按钮状态，供 QuotesPage 调用。"""

    def __init__(self, page: WatchlistHost) -> None:
        self._page = page
        self.keys: set[tuple[str, Exchange]] = set()

    def _service(self) -> WatchlistService | None:
        return self._page._get_watchlist_service()

    def refresh_keys(self) -> None:
        service = self._service()
        if service is None:
            self.keys = set()
            return
        self.keys = {(row["symbol"], Exchange(row["exchange"])) for row in service.get_items()}

    def contains(self, item: StockItem) -> bool:
        """标的是否在自选池（自选页列表即自选池，不依赖 keys 缓存）。"""
        if self._page.page_name == "自选":
            return True
        return (item.symbol, item.exchange) in self.keys

    def index_of(self, item: StockItem) -> int | None:
        key = (item.symbol, item.exchange)
        for index, stock in enumerate(self._page.all_stocks):
            if (stock.symbol, stock.exchange) == key:
                return index
        return None

    def update_action_buttons(self, item: StockItem | None) -> None:
        page = self._page
        if page.config.show_add_watchlist_button:
            if item is None:
                page.add_watchlist_button.setEnabled(False)
            else:
                key = (item.symbol, item.exchange)
                page.add_watchlist_button.setEnabled(key not in self.keys and len(self.keys) < WATCHLIST_MAX_ITEMS)
        if page.config.show_remove_watchlist_button:
            page.remove_watchlist_button.setEnabled(item is not None)
        if page.config.show_watchlist_move_buttons:
            index = self.index_of(item) if item is not None else None
            total = len(page.all_stocks)
            can_move = item is not None and not (page._watchlist_groups is not None and page._watchlist_groups.is_filtering())
            page.move_watchlist_up_button.setEnabled(can_move and index is not None and index > 0)
            page.move_watchlist_down_button.setEnabled(can_move and index is not None and index + 1 < total)

    def _pool_from_service(self) -> list[StockItem]:
        service = self._service()
        if service is None:
            return []
        return [
            StockItem(
                symbol=row["symbol"],
                exchange=Exchange(row["exchange"]),
                name=row["name"],
            )
            for row in service.get_items()
        ]

    def _apply_pool(self, pool: list[StockItem]) -> None:
        """从 service 结果刷新自选列表 UI（避免 load_stock_list 全量重载）。"""
        page = self._page
        bootstrap = getattr(page, "_watchlist_bootstrap", None)
        if isinstance(bootstrap, WatchlistBootstrapCoordinator):
            bootstrap.on_pool_ready(page, pool, source="pool_mutation")
            return
        page.watchlist_pool_stocks = pool
        if page._watchlist_groups is not None:
            page._watchlist_groups.on_stock_list_loaded(pool)
        else:
            page.all_stocks = pool
            page.apply_filter()
        self.refresh_keys()
        page._update_action_buttons()
        feature = getattr(page, "_watchlist_feature", None)
        if feature is not None:
            feature.refresh_context_bar()

    def add_selected(self) -> None:
        if not self._page.current_item:
            return
        service = self._service()
        if service is None:
            self._page.status_label.setText("自选服务未就绪")
            return

        item = self._page.current_item
        quote = self._page.quote_map.get(item.tickflow_symbol)
        name = quote.name if quote and quote.name else item.name
        if not service.add(item.symbol, item.exchange, name):
            reason = service.add_failure_reason(item.symbol, item.exchange)
            if reason == "full":
                self._page.status_label.setText(f"自选池已满（最多 {WATCHLIST_MAX_ITEMS} 只）")
            else:
                self._page.status_label.setText(f"{format_vt_symbol_cn(item.symbol, item.exchange)} 已在自选池")
            return
        self.refresh_keys()
        self._page._update_action_buttons()
        if self._page._watchlist_groups is not None:
            self._page._watchlist_groups.add_item_to_active_group(item.symbol, item.exchange)
        status = f"已加入自选：{format_vt_symbol_cn(item.symbol, item.exchange)}"
        if self._page._watchlist_groups is not None and self._page._watchlist_groups.is_filtering():
            status += f"（已加入分组「{self._page._watchlist_groups.active_group_label()}」）"
        self._page.status_label.setText(status)

    def remove_selected(self) -> None:
        if not self._page.current_item:
            return
        service = self._service()
        if service is None:
            self._page.status_label.setText("自选服务未就绪")
            return

        item = self._page.current_item
        removed_vt = item.vt_symbol
        position_service = self._page._get_position_service()
        if position_service is not None and position_service.contains(item.symbol, item.exchange):
            answer = QtWidgets.QMessageBox.question(
                cast(QtWidgets.QWidget, self._page),
                "移出自选",
                f"{format_vt_symbol_cn(item.symbol, item.exchange)} 仍有持仓记录，是否一并移出？",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if answer == QtWidgets.QMessageBox.StandardButton.Yes:
                position_service.remove(item.symbol, item.exchange)
                self._page.position_cache.pop(item.vt_symbol, None)
                panel = getattr(self._page, "position_panel", None)
                if panel is not None:
                    panel.render_panel()
        if not service.remove(item.symbol, item.exchange):
            self._page.status_label.setText("移出失败：标的不在自选池")
            return
        self._page.current_item = None
        if self._page.depth_panel is not None:
            self._page.depth_panel.clear()
        self._page.status_label.setText(f"已移出自选：{format_vt_symbol_cn(item.symbol, item.exchange)}")
        self._apply_pool(self._pool_from_service())
        bootstrap = getattr(self._page, "_watchlist_bootstrap", None)
        if isinstance(bootstrap, WatchlistBootstrapCoordinator) and removed_vt:
            bootstrap.invalidate_symbols(self._page, [removed_vt])
        if self._page.config.show_watchlist_signals:
            self._page._signals.on_symbols_changed()

    def move_selected(self, direction: Literal["up", "down"]) -> None:
        if not self._page.current_item:
            return
        service = self._service()
        if service is None:
            self._page.status_label.setText("自选服务未就绪")
            return

        item = self._page.current_item
        key = (item.symbol, item.exchange)
        if not service.move(item.symbol, item.exchange, direction=direction):
            return
        key = (item.symbol, item.exchange)
        self._apply_pool(self._pool_from_service())
        self._page._select_stock_key(key)
        label = "上移" if direction == "up" else "下移"
        self._page.status_label.setText(f"{format_vt_symbol_cn(item.symbol, item.exchange)} 已{label}")
