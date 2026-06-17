"""单页行情外壳（无内置侧栏，供主窗口左侧菜单切换）。"""

from __future__ import annotations

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ui.quotes.features.market_rank_sidebar import sync_rank_splitter_for_expansion
from vnpy_ashare.ui.quotes.market_discovery import MarketDiscoveryController, MarketDiscoveryStrip
from vnpy_ashare.ui.quotes.market_overview import MarketOverviewController, MarketOverviewPanel
from vnpy_ashare.ui.quotes.market_overview.header import MarketHeaderPanel
from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage
from vnpy_ashare.ui.quotes.watchlist_signals import restore_center_splitter
from vnpy_common.ui.qt_helpers import thread_is_active
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.build_extra import build_market_page_stylesheet


class QuotesShellWidget(QtWidgets.QWidget):
    """包装 QuotesPage；市场页附带顶部大盘概览带。"""

    PAGE_NAME: str = ""

    _thread_active = staticmethod(thread_is_active)

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("MarketRoot")

        self.page = QuotesPage(self.PAGE_NAME, self, event_engine=event_engine)
        self._overview_controller: MarketOverviewController | None = None
        self._header_panel: MarketHeaderPanel | None = None
        self._discovery_controller: MarketDiscoveryController | None = None

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        if self.PAGE_NAME == "市场":
            overview = MarketOverviewPanel(self)
            discovery = MarketDiscoveryStrip(self)
            self._header_panel = MarketHeaderPanel(overview, discovery, self)
            self._overview_controller = MarketOverviewController(self.page, overview)
            self._discovery_controller = MarketDiscoveryController(self.page, discovery)
            self.page.set_market_industry_filter_listener(self._overview_controller.sync_industry_filter)
            theme_manager().bind_stylesheet(self, extra=build_market_page_stylesheet)
            root.addWidget(self._header_panel)

        root.addWidget(self.page, stretch=1)

    @property
    def overview_controller(self) -> MarketOverviewController | None:
        return self._overview_controller

    def activate(self) -> None:
        self.page.activate()
        if self._overview_controller is not None:
            self._overview_controller.activate()
        if self._discovery_controller is not None:
            self._discovery_controller.activate()
        if self.page.config.show_watchlist_signals or self.page.config.show_watchlist_positions or self.page.config.show_run_output_panel:
            QtCore.QTimer.singleShot(0, lambda: restore_center_splitter(self.page))
        if self.PAGE_NAME == "市场":
            sidebar = self.page.rank_sidebar
            if sidebar is not None:
                QtCore.QTimer.singleShot(
                    0,
                    lambda: sync_rank_splitter_for_expansion(self.page, sidebar.is_expanded()),
                )

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        if self.page.config.show_watchlist_signals or self.page.config.show_watchlist_positions or self.page.config.show_run_output_panel:
            QtCore.QTimer.singleShot(0, lambda: restore_center_splitter(self.page))
        if self.PAGE_NAME == "市场":
            sidebar = self.page.rank_sidebar
            if sidebar is not None:
                QtCore.QTimer.singleShot(
                    0,
                    lambda: sync_rank_splitter_for_expansion(self.page, sidebar.is_expanded()),
                )

    def deactivate(self) -> None:
        self.page.deactivate()
        if self._overview_controller is not None:
            self._overview_controller.deactivate()
        if self._discovery_controller is not None:
            self._discovery_controller.deactivate()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.deactivate()
        super().closeEvent(event)


class MarketPageWidget(QuotesShellWidget):
    PAGE_NAME = "市场"


class RadarPageWidget(QuotesShellWidget):
    PAGE_NAME = "雷达"


class WatchlistPageWidget(QuotesShellWidget):
    PAGE_NAME = "自选"


class LocalPageWidget(QuotesShellWidget):
    PAGE_NAME = "本地"
