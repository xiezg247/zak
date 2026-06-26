"""QuotesPage 构造期状态、Controller 与 Timer 初始化。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.config.preferences.strategy_profile import bootstrap_strategy_profile
from vnpy_ashare.config.preferences.watchlist_position import load_watchlist_position_config
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
from vnpy_ashare.ui.quotes.features.strategy_monitor import StrategyMonitorPageFeature
from vnpy_ashare.ui.quotes.features.watchlist import WatchlistPageFeature
from vnpy_ashare.ui.quotes.features.watchlist.lazy_build import WatchlistLazyBuildCoordinator
from vnpy_ashare.ui.quotes.features.watchlist_panels import WatchlistPanelsFeature
from vnpy_ashare.ui.quotes.page.config import (
    MARKET_AUTO_REFRESH_DEFAULT,
    MARKET_SCROLL_DEBOUNCE_MS,
    PAGE_CONFIGS,
    SEARCH_DEBOUNCE_MS,
)
from vnpy_ashare.ui.quotes.page.roles import STRATEGY_MONITOR_PAGE, WATCHLIST_PAGE, uses_watchlist_pool
from vnpy_ashare.ui.quotes.watchlist.bootstrap import WatchlistBootstrapCoordinator
from vnpy_ashare.ui.quotes.watchlist.refresh_scheduler import WatchlistStrategyRefreshScheduler
from vnpy_ashare.ui.quotes.watchlist.strategy_batch import WatchlistStrategyBatchCoordinator
from vnpy_ashare.ui.quotes.watchlist_groups.controller import WatchlistGroupController
from vnpy_ashare.ui.quotes.watchlist_multiview.controller import WatchlistMultiViewController
from vnpy_ashare.ui.quotes.watchlist_positions.controller import WatchlistPositionController
from vnpy_ashare.ui.quotes.watchlist_signals.controller import WatchlistSignalController
from vnpy_common.ui.feedback import TaskGuard
from vnpy_common.ui.theme.manager import theme_manager

if TYPE_CHECKING:
    from vnpy.event import EventEngine

    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


def init_page_config(page: QuotesPage, page_name: str, *, event_engine: EventEngine | None) -> None:
    page.config = PAGE_CONFIGS[page_name]
    page.page_name = page_name
    page.event_engine = event_engine


def init_page_state(page: QuotesPage) -> None:
    page.all_stocks = []
    page.watchlist_pool_stocks = []
    page.display_stocks = []
    page.quote_map = {}
    page.downloaded_keys = set()
    page.bar_meta = {}
    page.bar_list_status = {}
    page._selected_gap_result = None
    page.current_item = None
    page.signal_config = bootstrap_strategy_profile()
    page.position_config = load_watchlist_position_config()
    page.signal_cache = {}
    page.continuation_cache = {}
    page.strategy_workspace_button = None
    page._strategy_workspace_open = False
    page._signal_cache_config = None
    page.position_cache = {}
    page._position_cache_config = None
    page._retired_workers = []
    page._load_generation = 0
    page._bars_generation = 0
    page._bars_request_id = 0
    page._active = False
    page._market_page = 0
    page._market_total = 0
    page._local_total = 0
    page._market_board = None
    page._market_rank_id = page.config.default_rank_id
    page._market_catalog = []
    page._market_catalog_quotes = {}
    page._market_catalog_loaded = False
    page._market_full_load_quiet = True
    page._market_updated_at = None
    page._market_page_cache = {}
    page._market_count_cache = {}
    page._market_loading_more = False
    page._market_load_mode = "rank"
    page._market_scroll_blocked = False
    page._market_last_load_more_at = 0.0
    page._apply_default_table_sort = False
    page._market_table_host = None
    page._market_matched = []
    page._market_board_base = None
    page._market_board_base_key = None
    page._market_filter_keyword = ""
    page._local_filter_keyword = ""
    page._market_industry_filter = None
    page._market_vt_whitelist = None
    page._market_drilldown_label = None
    page._pending_industry_drilldown = None
    page._pending_concept_drilldown = None
    page._industry_map_cache = None
    page._market_board_map_cache = None
    page._market_industry_filter_listener = None
    page._market_auto_refresh = MARKET_AUTO_REFRESH_DEFAULT
    page._market_sort_column = None
    page._market_sort_ascending = True
    page._center_splitter_bound = False
    page.emotion_cycle_more_button = None
    page._watchlist_table_ratio_override = None
    page.column_button = None
    page.rank_sidebar = None
    page.rank_list = None
    page.chart = None
    page.signal_panel = None
    page.position_panel = None
    page.multiview_board = None
    page.view_table_button = None
    page.view_multiview_button = None
    page._center_view_stack = None
    page.stock_note_panel = None
    page.refresh_radar_button = None
    page.radar_ai_button = None
    page.radar_board = None
    page.radar_resonance_panel = None
    page._radar_controller = None
    page._radar_splitter = None
    page._radar_resonance_splitter_saved_state = None
    page._rank_splitter = None
    page._rank_splitter_filter = None

    page._load_worker = None
    page._market_worker = None
    page._prefetch_worker = None
    page._sync_worker = None
    page._bars_worker = None
    page._download_worker = None
    page._batch_fill_worker = None
    page._batch_gap_fill_worker = None
    page._gap_worker = None
    page._gap_generation = 0
    page._quotes_worker = None
    page._pending_quote_refresh = False
    page._watchlist_quotes_loading = False
    page._depth_worker = None
    page._diagnose_worker = None
    page._invalid_bar_cleanup_worker = None
    page._depth_generation = 0
    page._depth_permission_denied = False
    page.depth_panel = None
    page.diagnose_panel = None
    page.chart_panel = None
    page.chart_section = None
    page.chart_hint = None
    page._right_panel_widget = None
    page._chart_splitter_saved_state = None
    page.run_output_panel = None
    page._center_splitter = None
    page._stream_bridge = None
    page._stream_fallback = False
    page._local_scope = "daily"
    page._splitter = None
    page._column_menu = None
    page._stats_label = None
    page._open_label = None
    page._high_label = None
    page._low_label = None
    page._volume_label = None


def init_controllers(page: QuotesPage, page_name: str) -> None:
    page._watchlist = WatchlistController(page)
    page._pagination = MarketPaginationController(page)
    page._stream = QuoteStreamController(page)
    page._local = LocalDataController(page)
    page._table = TableController(page)
    page._actions = ActionsController(page)
    page._batch_backtest = WatchlistBatchBacktestController(page)
    page._signals = WatchlistSignalController(page)
    page._positions = WatchlistPositionController(page)
    page._multiview = WatchlistMultiViewController(page)
    page._strategy_refresh = WatchlistStrategyRefreshScheduler(page, page._signals, page._positions)
    page._strategy_batch = WatchlistStrategyBatchCoordinator(page) if page_name == STRATEGY_MONITOR_PAGE else None
    page._watchlist_groups = None
    page._loader = DataLoaderController(page)
    page._market_rank = MarketRankFeature(page)
    page._watchlist_panels = WatchlistPanelsFeature(page)
    page._watchlist_feature = WatchlistPageFeature(page) if page_name == WATCHLIST_PAGE else None
    page._strategy_monitor_feature = StrategyMonitorPageFeature(page) if page_name == STRATEGY_MONITOR_PAGE else None
    page._watchlist_bootstrap = WatchlistBootstrapCoordinator() if uses_watchlist_pool(page_name) else None
    page._watchlist_lazy = WatchlistLazyBuildCoordinator() if page_name == WATCHLIST_PAGE else None
    page._stock_notes = StockNotesFeature(page)


def init_timers(page: QuotesPage) -> None:
    page._search_timer = QtCore.QTimer(page)
    page._search_timer.setSingleShot(True)
    page._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
    page._search_timer.timeout.connect(page.apply_filter)

    page._quote_timer = QtCore.QTimer(page)
    page._quote_timer.setSingleShot(True)
    page._quote_timer.timeout.connect(page.refresh_quotes)

    page._market_scroll_timer = QtCore.QTimer(page)
    page._market_scroll_timer.setSingleShot(True)
    page._market_scroll_timer.setInterval(MARKET_SCROLL_DEBOUNCE_MS)
    page._market_scroll_timer.timeout.connect(page._check_market_scroll_load)

    page._market_cache_sync_timer = QtCore.QTimer(page)
    page._market_cache_sync_timer.setSingleShot(True)
    page._market_cache_sync_timer.setInterval(400)
    page._market_cache_sync_timer.timeout.connect(page._loader.flush_market_cache_sync)


def finish_page_init(page: QuotesPage) -> None:
    page._task_guard = TaskGuard(page._toast)
    page._task_lock_table = True
    page._task_lock_search = True
    page._active_worker_attr = None
    theme_manager().register_callback(page._on_theme_changed)


def wire_page_features(page: QuotesPage) -> None:
    if page.config.show_watchlist_groups:
        page._watchlist_groups = WatchlistGroupController(page)
        page._watchlist_groups.wire()
    if page._watchlist_feature is not None:
        page._watchlist_feature.wire()
    if getattr(page, "_strategy_monitor_feature", None) is not None:
        page._strategy_monitor_feature.wire()
