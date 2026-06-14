"""选股页数据状态条与结果洞察面板。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.screener.data.screening_status import (
    ScreeningDataStatus,
    build_run_insight_detail,
    build_screening_data_status,
)
from vnpy_ashare.ui.screener.workers.screener_workers import QuoteRefreshWorker
from vnpy_common.ui.qt_helpers import release_thread


class ScreeningDataStatusBar(QtWidgets.QWidget):
    """展示交易时段 / 数据源 / 快照年龄，交易时段可一键刷新行情。"""

    refresh_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ScreeningDataStatusBar")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(8)

        self._label = QtWidgets.QLabel()
        self._label.setObjectName("ScreenerHint")
        self._label.setWordWrap(True)
        layout.addWidget(self._label, stretch=1)

        self._refresh_btn = QtWidgets.QPushButton("刷新行情")
        self._refresh_btn.setObjectName("SecondaryButton")
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(self._refresh_btn)

    def apply_status(self, status: ScreeningDataStatus) -> None:
        self._label.setText(status.summary_line())
        self._refresh_btn.setVisible(status.can_refresh_quotes)

    def refresh(self, *, uses_live_quotes: bool = True) -> None:
        self.apply_status(build_screening_data_status(uses_live_quotes=uses_live_quotes))

    def set_refresh_enabled(self, enabled: bool) -> None:
        self._refresh_btn.setEnabled(enabled)


class ScreenerResultInsights(QtWidgets.QWidget):
    """结果区上方：行业分布 + 较上次 diff 摘要。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ScreenerResultInsights")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(0)

        self._label = QtWidgets.QLabel()
        self._label.setObjectName("ResultSummary")
        self._label.setWordWrap(True)
        layout.addWidget(self._label)
        self.hide()

    def apply(self, rows: list[dict[str, Any]], config: dict[str, Any] | None = None) -> None:
        text = build_run_insight_detail(rows, config)
        self._label.setText(text)
        self.setVisible(bool(text))

    def clear(self) -> None:
        self._label.clear()
        self.hide()


class ScreeningPageStatusController(QtCore.QObject):
    """管理数据状态条刷新与一键拉行情（策略/自动选股页共用）。"""

    def __init__(
        self,
        page: QtWidgets.QWidget,
        status_bar: ScreeningDataStatusBar,
        *,
        uses_live_quotes: Callable[[], bool],
        on_log: Callable[[str], None] | None = None,
        on_toast_error: Callable[[str], None] | None = None,
        on_toast_success: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(page)
        self._page = page
        self._status_bar = status_bar
        self._uses_live_quotes = uses_live_quotes
        self._on_log = on_log
        self._on_toast_error = on_toast_error
        self._on_toast_success = on_toast_success
        self._quote_worker: QuoteRefreshWorker | None = None
        self._retired_workers: list[QtCore.QThread] = []
        self._session_timer = QtCore.QTimer(self)
        self._session_timer.setInterval(30_000)
        self._session_timer.timeout.connect(self.refresh_status)
        status_bar.refresh_requested.connect(self._refresh_quotes)

    def activate(self) -> None:
        self.refresh_status()
        self._session_timer.start()

    def deactivate(self) -> None:
        self._session_timer.stop()
        if self._quote_worker is not None:
            self._quote_worker.requestInterruption()
            release_thread(self._retired_workers, self._quote_worker, timeout_ms=0)
            self._quote_worker = None

    def refresh_status(self) -> None:
        self._status_bar.refresh(uses_live_quotes=self._uses_live_quotes())

    def _refresh_quotes(self) -> None:
        if self._quote_worker is not None and self._quote_worker.isRunning():
            return
        self._status_bar.set_refresh_enabled(False)
        worker = QuoteRefreshWorker(parent=self._page)
        self._quote_worker = worker

        def on_finished(ok: bool, message: str) -> None:
            if self._quote_worker is worker:
                self._quote_worker = None
            release_thread(self._retired_workers, worker)
            self._status_bar.set_refresh_enabled(True)
            self.refresh_status()
            if self._on_log and message:
                self._on_log(message)
            if ok:
                if self._on_toast_success:
                    self._on_toast_success(message or "行情已刷新")
            elif self._on_toast_error:
                self._on_toast_error(message or "行情刷新失败")

        worker.finished.connect(on_finished)
        worker.start()
