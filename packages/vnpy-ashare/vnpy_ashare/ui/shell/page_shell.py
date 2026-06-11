"""单页行情外壳（无内置侧栏，供主窗口左侧菜单切换）。"""

from __future__ import annotations

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage
from vnpy_ashare.ui.quotes.watchlist_signals import restore_center_splitter
from vnpy_ashare.ui.quotes.workers import IndexQuotesWorker
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import quote_change_color

INDEX_REFRESH_MS = 30000


class QuotesShellWidget(QtWidgets.QWidget):
    """包装 QuotesPage；市场页附带底部指数栏。"""

    PAGE_NAME: str = ""

    _thread_active = staticmethod(thread_is_active)

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("MarketRoot")

        self.page = QuotesPage(self.PAGE_NAME, self, event_engine=event_engine)
        self._index_worker: IndexQuotesWorker | None = None
        self._retired_workers: list[QtCore.QThread] = []
        self._index_timer: QtCore.QTimer | None = None
        self._index_rows: list = []
        self.index_ticker: QtWidgets.QLabel | None = None

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        if self.PAGE_NAME == "市场":
            self.index_ticker = QtWidgets.QLabel("指数加载中...")
            self.index_ticker.setObjectName("IndexTicker")
            root.addWidget(self.index_ticker)

            self._index_timer = QtCore.QTimer(self)
            self._index_timer.setInterval(INDEX_REFRESH_MS)
            self._index_timer.timeout.connect(self.refresh_indices)
            theme_manager().register_callback(self._on_theme_changed)

        root.addWidget(self.page, stretch=1)

    def _on_theme_changed(self, tokens) -> None:
        if self.index_ticker is None or not self._index_rows:
            return
        self._render_index_ticker(self._index_rows, tokens=tokens)

    def _render_index_ticker(self, rows: list, *, tokens=None) -> None:
        if self.index_ticker is None:
            return
        if tokens is None:
            tokens = theme_manager().tokens()
        parts: list[str] = []
        for label, quote in rows:
            color = quote_change_color(quote, tokens)
            pct = quote.change_pct
            parts.append(f'<span style="color:{color}">{label} {quote.last_price:.2f} {pct:+.2f}%</span>')
        self.index_ticker.setText("  |  ".join(parts) if parts else "指数暂无数据")

    def activate(self) -> None:
        self.page.activate()
        if self._index_timer is not None:
            QtCore.QTimer.singleShot(500, self.refresh_indices)
            self._index_timer.start()
        if (
            self.page.config.show_watchlist_signals
            or self.page.config.show_watchlist_positions
            or self.page.config.show_run_output_panel
        ):
            QtCore.QTimer.singleShot(0, lambda: restore_center_splitter(self.page))

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        if (
            self.page.config.show_watchlist_signals
            or self.page.config.show_watchlist_positions
            or self.page.config.show_run_output_panel
        ):
            QtCore.QTimer.singleShot(0, lambda: restore_center_splitter(self.page))

    def deactivate(self) -> None:
        self.page.deactivate()
        if self._index_timer is not None:
            self._index_timer.stop()
        worker = self._index_worker
        self._index_worker = None
        release_thread(self._retired_workers, worker, timeout_ms=0)

    def refresh_indices(self) -> None:
        if self.index_ticker is None or self._thread_active(self._index_worker):
            return

        worker = IndexQuotesWorker()
        self._index_worker = worker

        def on_finished(rows: list) -> None:
            if self._index_worker is worker:
                self._index_worker = None
            release_thread(self._retired_workers, worker)
            self._index_rows = rows
            self._render_index_ticker(rows)

        def on_failed(_msg: str) -> None:
            if self._index_worker is worker:
                self._index_worker = None
            release_thread(self._retired_workers, worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.deactivate()
        super().closeEvent(event)


class MarketPageWidget(QuotesShellWidget):
    PAGE_NAME = "市场"


class WatchlistPageWidget(QuotesShellWidget):
    PAGE_NAME = "自选"


class LocalPageWidget(QuotesShellWidget):
    PAGE_NAME = "本地"
