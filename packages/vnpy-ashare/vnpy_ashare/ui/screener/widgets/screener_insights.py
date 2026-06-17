"""选股页数据状态条与结果洞察面板。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.screener.result_row import ScreeningRowLike
from vnpy_ashare.screener.data.screening_status import (
    ScreeningDataStatus,
    build_run_insight_detail,
    build_screening_data_status,
)
from vnpy_ashare.ui.screener.widgets.screener_config_section import (
    load_config_section_expanded,
    save_config_section_expanded,
)
from vnpy_ashare.ui.screener.widgets.sector_distribution_panel import SectorDistributionPanel
from vnpy_ashare.ui.screener.workers.screener_workers import QuoteRefreshWorker
from vnpy_common.ui.qt_helpers import release_thread
from vnpy_common.ui.theme import theme_manager

_RESULT_INSIGHTS_SECTION_ID = "result_insights"


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
    """结果区上方：可折叠的行业分布 + 较上次 diff 摘要。"""

    expansion_changed = QtCore.Signal(bool)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ScreenerResultInsights")
        self._expanded = load_config_section_expanded(_RESULT_INSIGHTS_SECTION_ID, True)
        self._summary_text = ""

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 6)
        root.setSpacing(4)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)
        self._collapse_button = QtWidgets.QToolButton(self)
        self._collapse_button.setObjectName("ScreenerConfigSectionToggle")
        self._collapse_button.setCheckable(True)
        self._collapse_button.clicked.connect(self._on_collapse_toggled)
        header.addWidget(self._collapse_button)

        title = QtWidgets.QLabel("结果洞察")
        title.setObjectName("ScreenerSectionLabel")
        header.addWidget(title)

        self._inline_summary = QtWidgets.QLabel("")
        self._inline_summary.setObjectName("ScreenerHint")
        self._inline_summary.setWordWrap(False)
        header.addWidget(self._inline_summary, stretch=1)
        root.addLayout(header)

        self._content_host = QtWidgets.QWidget(self)
        self._content_host.setObjectName("ScreenerResultInsightsContent")
        content_layout = QtWidgets.QVBoxLayout(self._content_host)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._label = QtWidgets.QLabel()
        self._label.setObjectName("ResultSummary")
        self._label.setWordWrap(True)
        content_layout.addWidget(self._label)

        self._sector_panel = SectorDistributionPanel(self._content_host)
        content_layout.addWidget(self._sector_panel)
        root.addWidget(self._content_host)

        theme_manager().bind_stylesheet(self)
        self.set_expanded(self._expanded, emit=False, persist=False)
        self.hide()

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, *, emit: bool = True, persist: bool = True) -> None:
        changed = self._expanded != expanded
        self._expanded = expanded
        self._sync_collapse_button()
        self._content_host.setVisible(expanded)
        self._update_inline_summary()
        if persist and changed:
            save_config_section_expanded(_RESULT_INSIGHTS_SECTION_ID, expanded)
        if emit and changed:
            self.expansion_changed.emit(expanded)

    def apply(self, rows: Sequence[ScreeningRowLike], config: dict[str, Any] | None = None) -> None:
        text = build_run_insight_detail(rows, config)
        self._summary_text = text
        self._label.setText(text)
        self._sector_panel.apply_rows(rows)
        has_content = bool(text) or self._sector_panel.isVisible()
        self.setVisible(has_content)
        if has_content:
            self._update_inline_summary()

    def clear(self) -> None:
        self._summary_text = ""
        self._label.clear()
        self._sector_panel.clear()
        self._inline_summary.clear()
        self.hide()

    def _update_inline_summary(self) -> None:
        if self._expanded or not self.isVisible():
            self._inline_summary.hide()
            return
        if self._summary_text:
            line = self._summary_text.replace("\n", " · ")
            if len(line) > 96:
                line = f"{line[:93]}…"
            self._inline_summary.setText(line)
            self._inline_summary.show()
            return
        if self._sector_panel.isVisible():
            self._inline_summary.setText("行业分布")
            self._inline_summary.show()
            return
        self._inline_summary.hide()

    def _sync_collapse_button(self) -> None:
        self._collapse_button.blockSignals(True)
        self._collapse_button.setChecked(self._expanded)
        self._collapse_button.setArrowType(QtCore.Qt.ArrowType.DownArrow if self._expanded else QtCore.Qt.ArrowType.RightArrow)
        self._collapse_button.blockSignals(False)

    def _on_collapse_toggled(self, expanded: bool) -> None:
        self.set_expanded(expanded)


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
