"""自选页 Host 协议：controller / panel 对 QuotesPage 的窄接口。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.quotes.watchlist.pool_host import WatchlistPoolHost

if TYPE_CHECKING:
    from vnpy.trader.engine import MainEngine

    from vnpy_ashare.config.preferences.watchlist_position import WatchlistPositionConfig
    from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
    from vnpy_ashare.domain.data.bar_health import BarMeta
    from vnpy_ashare.domain.symbols.stock import StockItem
    from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
    from vnpy_ashare.services.analysis import AnalysisService
    from vnpy_ashare.ui.quotes.chart.panel import ChartPanel
    from vnpy_ashare.ui.quotes.controllers.watchlist import WatchlistController
    from vnpy_ashare.ui.quotes.features.watchlist import WatchlistPageFeature
    from vnpy_ashare.ui.quotes.watchlist_multiview.controller import WatchlistMultiViewController
    from vnpy_ashare.ui.quotes.watchlist_positions.controller import WatchlistPositionController
    from vnpy_ashare.ui.quotes.watchlist_signals.panel import WatchlistSignalPanel
    from vnpy_common.ui.feedback import PageToastHost


@runtime_checkable
class WatchlistHost(WatchlistPoolHost, Protocol):
    """QuotesPage 在自选页场景下对子 controller 暴露的能力集（扩展 WatchlistPoolHost）。"""

    bar_meta: dict[tuple[str, Exchange], BarMeta]
    market_table: QtWidgets.QTableView
    signal_cache: dict[str, SignalSnapshot]
    signal_config: WatchlistSignalConfig
    position_config: WatchlistPositionConfig
    chart_panel: ChartPanel | None
    signal_panel: WatchlistSignalPanel | None
    _active: bool
    _signal_cache_config: WatchlistSignalConfig | None
    _position_cache_config: WatchlistSignalConfig | None
    _retired_workers: list[QtCore.QThread]
    _positions: WatchlistPositionController
    _multiview: WatchlistMultiViewController
    _toast: PageToastHost
    _watchlist_feature: WatchlistPageFeature | None
    _watchlist: WatchlistController
    _watchlist_table_ratio_override: float | None
    display_stocks: list[StockItem]
    multiview_board: Any
    _center_view_stack: Any
    _market_table_host: Any
    view_table_button: Any
    view_multiview_button: Any
    _stats_label: Any
    _actions: Any
    watchlist_group_tab_bar: Any
    watchlist_pool_context_bar: Any
    _center_splitter: Any
    run_output_panel: Any
    _watchlist_groups: Any
    event_engine: Any
    emotion_cycle_more_button: QtWidgets.QPushButton | None
    risk_gate_more_button: QtWidgets.QPushButton | None

    def find_stock_item(self, vt_symbol: str) -> StockItem | None: ...

    def watchlist_pool_items(self) -> list[StockItem]: ...

    def _get_analysis_service(self) -> AnalysisService | None: ...

    def _get_main_engine(self) -> MainEngine | None: ...

    def _refresh_risk_gate_chip(self) -> None: ...

    def apply_strategy_profile(self, profile_id: str) -> None: ...

    def apply_signal_panel_config(self) -> None: ...

    def _wire_multiview(self) -> None: ...

    def _wire_signal_panel(self) -> None: ...

    def _wire_position_panel(self) -> None: ...

    def load_stock_list(self) -> None: ...
