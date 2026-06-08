"""单页行情外壳（无内置侧栏，供主窗口左侧菜单切换）。"""

from __future__ import annotations

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ui.quotes_page import QuotesPage
from vnpy_ashare.ui.styles import FALL_COLOR, FLAT_COLOR, RISE_COLOR, TERMINAL_STYLESHEET
from vnpy_ashare.ui.worker import IndexQuotesWorker

INDEX_REFRESH_MS = 30000


class QuotesShellWidget(QtWidgets.QWidget):
    """包装 QuotesPage；市场页附带底部指数栏。"""

    PAGE_NAME: str = ""

    @staticmethod
    def _thread_active(worker: QtCore.QThread | None) -> bool:
        if worker is None:
            return False
        try:
            return worker.isRunning()
        except RuntimeError:
            return False

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("MarketRoot")

        self.page = QuotesPage(self.PAGE_NAME, self, event_engine=event_engine)
        self._index_worker: IndexQuotesWorker | None = None
        self._index_timer: QtCore.QTimer | None = None
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

        root.addWidget(self.page, stretch=1)

        self.setStyleSheet(TERMINAL_STYLESHEET)

    def activate(self) -> None:
        self.page.activate()
        if self._index_timer is not None:
            QtCore.QTimer.singleShot(500, self.refresh_indices)
            self._index_timer.start()

    def deactivate(self) -> None:
        self.page.deactivate()
        if self._index_timer is not None:
            self._index_timer.stop()

    def refresh_indices(self) -> None:
        if self.index_ticker is None or self._thread_active(self._index_worker):
            return

        worker = IndexQuotesWorker()
        self._index_worker = worker

        def on_finished(rows: list) -> None:
            if self._index_worker is worker:
                self._index_worker = None
            parts: list[str] = []
            for label, quote in rows:
                color = RISE_COLOR if quote.is_rise else FALL_COLOR if quote.is_fall else FLAT_COLOR
                pct = quote.change_pct
                parts.append(
                    f'<span style="color:{color}">{label} {quote.last_price:.2f} '
                    f'{pct:+.2f}%</span>'
                )
            if self.index_ticker is not None:
                self.index_ticker.setText("  |  ".join(parts) if parts else "指数暂无数据")

        def on_failed(_msg: str) -> None:
            if self._index_worker is worker:
                self._index_worker = None

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
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
