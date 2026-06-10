"""自选池 UI 控制器（委托 WatchlistService）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from vnpy.trader.constant import Exchange

from vnpy_ashare.config import format_vt_symbol_cn
from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.services.watchlist_service import WatchlistService

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.quotes_page import QuotesPage


class WatchlistController:
    """封装自选 CRUD 与按钮状态，供 QuotesPage 调用。"""

    def __init__(self, page: QuotesPage) -> None:
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
                page.add_watchlist_button.setEnabled(key not in self.keys)
        if page.config.show_remove_watchlist_button:
            page.remove_watchlist_button.setEnabled(item is not None)
        if page.config.show_watchlist_move_buttons:
            index = self.index_of(item) if item is not None else None
            total = len(page.all_stocks)
            page.move_watchlist_up_button.setEnabled(item is not None and index is not None and index > 0)
            page.move_watchlist_down_button.setEnabled(item is not None and index is not None and index + 1 < total)

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
            self._page.status_label.setText(f"{format_vt_symbol_cn(item.symbol, item.exchange)} 已在自选池")
            return
        self.refresh_keys()
        self._page._update_action_buttons()
        self._page.status_label.setText(f"已加入自选：{format_vt_symbol_cn(item.symbol, item.exchange)}")

    def remove_selected(self) -> None:
        if not self._page.current_item:
            return
        service = self._service()
        if service is None:
            self._page.status_label.setText("自选服务未就绪")
            return

        item = self._page.current_item
        if not service.remove(item.symbol, item.exchange):
            self._page.status_label.setText("移出失败：标的不在自选池")
            return
        self._page.current_item = None
        if self._page.depth_panel is not None:
            self._page.depth_panel.clear()
        self._page.status_label.setText(f"已移出自选：{format_vt_symbol_cn(item.symbol, item.exchange)}")
        self._page.load_stock_list()

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
        self._page.all_stocks = [
            StockItem(
                symbol=row["symbol"],
                exchange=Exchange(row["exchange"]),
                name=row["name"],
            )
            for row in service.get_items()
        ]
        self._page.apply_filter()
        self._page._select_stock_key(key)
        label = "上移" if direction == "up" else "下移"
        self._page.status_label.setText(f"{format_vt_symbol_cn(item.symbol, item.exchange)} 已{label}")
