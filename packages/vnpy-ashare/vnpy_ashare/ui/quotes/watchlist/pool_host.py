"""自选池 Host 协议：跨页（行情/自选等）WatchlistController 对页面的窄接口。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from vnpy.trader.constant import Exchange

if TYPE_CHECKING:
    from vnpy_ashare.domain.symbols.stock import StockItem
    from vnpy_ashare.domain.trading.position_snapshot import PositionSnapshot
    from vnpy_ashare.quotes.core.models import QuoteSnapshot
    from vnpy_ashare.services.position import PositionService
    from vnpy_ashare.services.watchlist import WatchlistService
    from vnpy_ashare.ui.quotes.page.config import PageConfig
    from vnpy_ashare.ui.quotes.watchlist_groups.controller import WatchlistGroupController
    from vnpy_ashare.ui.quotes.watchlist_signals.controller import WatchlistSignalController


@runtime_checkable
class WatchlistPoolHost(Protocol):
    """QuotesPage 暴露给 WatchlistController 的最小能力集（不限于自选页）。"""

    page_name: str
    config: PageConfig
    all_stocks: list[StockItem]
    watchlist_pool_stocks: list[StockItem]
    current_item: StockItem | None
    quote_map: dict[str, QuoteSnapshot]
    position_cache: dict[str, PositionSnapshot]
    status_label: Any
    depth_panel: Any
    position_panel: Any
    add_watchlist_button: Any
    remove_watchlist_button: Any
    move_watchlist_up_button: Any
    move_watchlist_down_button: Any
    _watchlist_groups: WatchlistGroupController | None
    _watchlist_feature: Any
    _signals: WatchlistSignalController

    def _get_watchlist_service(self) -> WatchlistService | None: ...

    def _get_position_service(self) -> PositionService | None: ...

    def apply_filter(self) -> None: ...

    def _update_action_buttons(self) -> None: ...

    def _select_stock_key(self, key: tuple[str, Exchange]) -> None: ...
