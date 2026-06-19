"""QuotesPage 由 controller / feature 赋值的运行时属性（mixin，仅作 mypy 声明）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ui.components.task_run_output_panel import TaskRunOutputPanel
from vnpy_common.ui.feedback import TaskGuard

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.controllers.actions import ActionsController
    from vnpy_ashare.ui.quotes.controllers.batch_backtest import WatchlistBatchBacktestController
    from vnpy_ashare.ui.quotes.controllers.data_loader import DataLoaderController
    from vnpy_ashare.ui.quotes.controllers.local_data import LocalDataController
    from vnpy_ashare.ui.quotes.controllers.pagination import MarketPaginationController
    from vnpy_ashare.ui.quotes.controllers.quote_stream import QuoteStreamController
    from vnpy_ashare.ui.quotes.controllers.table import TableController
    from vnpy_ashare.ui.quotes.controllers.watchlist import WatchlistController
    from vnpy_ashare.ui.quotes.features.market_rank import MarketRankFeature
    from vnpy_ashare.ui.quotes.features.stock_notes import StockNotesFeature
    from vnpy_ashare.ui.quotes.features.watchlist import WatchlistPageFeature
    from vnpy_ashare.ui.quotes.features.watchlist_panels import WatchlistPanelsFeature
    from vnpy_ashare.ui.quotes.watchlist.bootstrap import WatchlistBootstrapCoordinator
    from vnpy_ashare.ui.quotes.watchlist.refresh_scheduler import WatchlistStrategyRefreshScheduler
    from vnpy_ashare.ui.quotes.watchlist.strategy_batch import WatchlistStrategyBatchCoordinator
    from vnpy_ashare.ui.quotes.watchlist_groups.controller import WatchlistGroupController
    from vnpy_ashare.ui.quotes.watchlist_multiview.controller import WatchlistMultiViewController
    from vnpy_ashare.ui.quotes.watchlist_positions.controller import WatchlistPositionController
    from vnpy_ashare.ui.quotes.watchlist_signals.controller import WatchlistSignalController


class QuotesPageControllerAttrs:
    """Controller 与子 feature 挂载到 QuotesPage 的状态与引用。"""

    _watchlist: WatchlistController
    _pagination: MarketPaginationController
    _stream: QuoteStreamController
    _local: LocalDataController
    _table: TableController
    _actions: ActionsController
    _batch_backtest: WatchlistBatchBacktestController
    _signals: WatchlistSignalController
    _positions: WatchlistPositionController
    _multiview: WatchlistMultiViewController
    _strategy_refresh: WatchlistStrategyRefreshScheduler
    _strategy_batch: WatchlistStrategyBatchCoordinator | None
    _loader: DataLoaderController
    _market_rank: MarketRankFeature
    _watchlist_panels: WatchlistPanelsFeature
    _watchlist_feature: WatchlistPageFeature | None
    _watchlist_bootstrap: WatchlistBootstrapCoordinator | None
    _stock_notes: StockNotesFeature
    _watchlist_groups: WatchlistGroupController | None
    _task_guard: TaskGuard

    _active: bool
    _market_page: int
    _market_total: int
    _local_total: int
    _market_catalog_loaded: bool
    _market_full_load_quiet: bool
    _market_loading_more: bool
    _market_load_mode: str
    _market_scroll_blocked: bool
    _market_last_load_more_at: float
    _apply_default_table_sort: bool
    _market_industry_filter_listener: Any
    _market_auto_refresh: bool
    _stream_fallback: bool
    _depth_permission_denied: bool
    _depth_generation: int
    _gap_generation: int
    _bars_generation: int
    _bars_request_id: int
    _load_generation: int
    _local_scope: str
    _watchlist_table_ratio_override: float | None

    _search_timer: QtCore.QTimer
    _quote_timer: QtCore.QTimer
    _more_menu_actions: dict[str, QtGui.QAction]

    run_output_panel: TaskRunOutputPanel | None
