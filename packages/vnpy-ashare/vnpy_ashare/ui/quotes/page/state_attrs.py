"""QuotesPage 构造期赋值的运行时状态（mixin，仅作 mypy 声明）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnpy.event import EventEngine
from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtCore

from vnpy_ashare.config.preferences.watchlist_position import WatchlistPositionConfig
from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
from vnpy_ashare.domain.data.bar_health import BarGapResult, BarHealthStatus, BarMeta
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.domain.trading.position import PositionSnapshot
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.domain.trading.stock_continuation import StockContinuationSnapshot
from vnpy_ashare.services.tickflow_quote import TickflowStreamBridge
from vnpy_ashare.ui.quotes.workers.quotes_workers import (
    BarGapCheckWorker,
    BarsLoadWorker,
    BatchFillWorker,
    BatchGapFillWorker,
    DepthRefreshWorker,
    DiagnoseWorker,
    DownloadWorker,
    InvalidBarCleanupWorker,
    MinuteDownloadWorker,
    QuotesRefreshWorker,
    ScopeBarsLoadWorker,
)

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.config import PageConfig


class QuotesPageStateAttrs:
    """init_page_config / init_page_state / init_timers 写入的字段。"""

    config: PageConfig
    page_name: str
    event_engine: EventEngine | None

    all_stocks: list[StockItem]
    watchlist_pool_stocks: list[StockItem]
    display_stocks: list[StockItem]
    quote_map: dict[str, QuoteSnapshot]
    downloaded_keys: set[tuple[str, Exchange]]
    bar_meta: dict[tuple[str, Exchange], BarMeta]
    bar_list_status: dict[tuple[str, Exchange], BarHealthStatus]
    _selected_gap_result: BarGapResult | None
    current_item: StockItem | None

    signal_config: WatchlistSignalConfig
    position_config: WatchlistPositionConfig
    signal_cache: dict[str, SignalSnapshot]
    continuation_cache: dict[str, StockContinuationSnapshot]
    position_cache: dict[str, PositionSnapshot]
    strategy_workspace_button: Any
    _strategy_workspace_open: bool
    _signal_cache_config: WatchlistSignalConfig | None
    _position_cache_config: WatchlistSignalConfig | None
    _retired_workers: list[QtCore.QThread]

    _market_board: str | None
    _market_rank_id: str
    _market_catalog: list[Any]
    _market_catalog_quotes: dict[Any, Any]
    _market_updated_at: str | None
    _market_page_cache: dict[Any, Any]
    _market_count_cache: dict[Any, Any]
    _market_matched: list[StockItem]
    _market_board_base: list[StockItem] | None
    _market_board_base_key: str | None
    _market_filter_keyword: str
    _local_filter_keyword: str
    _market_industry_filter: str | None
    _market_vt_whitelist: frozenset[str] | None
    _market_drilldown_label: str | None
    _pending_industry_drilldown: str | None
    _pending_concept_drilldown: frozenset[str] | None
    _industry_map_cache: dict[str, str] | None
    _market_board_map_cache: dict[str, str] | None
    emotion_cycle_more_button: Any

    _load_worker: QtCore.QThread | None
    _market_worker: QtCore.QThread | None
    _prefetch_worker: QtCore.QThread | None
    _sync_worker: QtCore.QThread | None
    _bars_worker: BarsLoadWorker | ScopeBarsLoadWorker | None
    _download_worker: DownloadWorker | MinuteDownloadWorker | None
    _batch_fill_worker: BatchFillWorker | None
    _batch_gap_fill_worker: BatchGapFillWorker | None
    _gap_worker: BarGapCheckWorker | None
    _quotes_worker: QuotesRefreshWorker | None
    _depth_worker: DepthRefreshWorker | None
    _diagnose_worker: DiagnoseWorker | None
    _invalid_bar_cleanup_worker: InvalidBarCleanupWorker | None

    chart_hint: Any
    _chart_splitter_saved_state: QtCore.QByteArray | None
    _radar_resonance_splitter_saved_state: QtCore.QByteArray | None
    _stream_bridge: TickflowStreamBridge | None
    _column_menu: Any
    _stats_label: Any
    _open_label: Any
    _high_label: Any
    _low_label: Any
    _volume_label: Any

    _market_scroll_timer: QtCore.QTimer
    _market_cache_sync_timer: QtCore.QTimer
    _task_lock_table: bool
    _active_worker_attr: str | None
