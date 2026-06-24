"""侧栏「信息流」页面。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ai.context.feed import sync_info_feed_context
from vnpy_ashare.app.engine_access import get_feed_service
from vnpy_ashare.ui.features.info_feed.subscription_panel import SubscriptionPanel
from vnpy_ashare.ui.features.info_feed.sync_worker import FeedSyncWorker
from vnpy_ashare.ui.features.info_feed.timeline_view import FeedTimelineView
from vnpy_common.ui.feedback import PageToastHost, page_notify
from vnpy_common.ui.panel_widgets import section_title
from vnpy_common.ui.qt_helpers import release_thread

if TYPE_CHECKING:
    from vnpy_ashare.services.feed import FeedService


class InfoFeedPageWidget(QtWidgets.QWidget):
    def __init__(self, main_engine: MainEngine, event_engine: EventEngine | None) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("InfoFeedPage")

        self._service = get_feed_service(main_engine)
        self._sync_worker: FeedSyncWorker | None = None
        self._retired_workers: list[QtCore.QThread] = []
        self._filter_subscription_id: str | None = None

        self._sync_btn = QtWidgets.QPushButton("立即同步", self)
        self._sync_btn.setObjectName("ActionButton")
        self._cookie_hint = QtWidgets.QLabel("", self)
        self._cookie_hint.setObjectName("InfoFeedCookieHint")
        self._cookie_hint.setWordWrap(True)
        self._cookie_hint.hide()

        toolbar = QtWidgets.QWidget(self)
        toolbar.setObjectName("InfoFeedToolbar")
        top = QtWidgets.QHBoxLayout(toolbar)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)
        top.addWidget(section_title("信息流"))
        top.addStretch()
        top.addWidget(self._sync_btn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 10)
        layout.setSpacing(10)
        layout.addWidget(toolbar)
        layout.addWidget(self._cookie_hint)
        self._toast = PageToastHost(self)
        layout.addWidget(self._toast)

        if self._service is None:
            body = QtWidgets.QLabel("A 股引擎未加载，无法使用信息流。", self)
            body.setObjectName("PageHint")
            layout.insertWidget(2, body, stretch=1)
            return

        self._timeline = FeedTimelineView(self._service, event_engine, self)
        self._subscriptions = SubscriptionPanel(self._service, self)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        splitter.setObjectName("InfoFeedSplitter")
        splitter.addWidget(self._subscriptions)
        splitter.addWidget(self._timeline)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([300, 760])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        layout.insertWidget(2, splitter, stretch=1)

        self._sync_btn.clicked.connect(self._on_sync)
        self._subscriptions.selection_changed.connect(self._on_subscription_selected)
        self._subscriptions.subscriptions_changed.connect(self._on_subscriptions_changed)

    def activate(self) -> None:
        if self._service is None:
            return
        sync_info_feed_context(self.main_engine)
        self._refresh_cookie_hint()
        self._subscriptions.refresh()
        self._apply_filters()

    def deactivate(self) -> None:
        worker = self._sync_worker
        self._sync_worker = None
        if worker is not None:
            release_thread(self._retired_workers, worker)

    def _refresh_cookie_hint(self) -> None:
        if self._service is None:
            return
        if self._service.cookies_configured():
            self._cookie_hint.hide()
        else:
            self._cookie_hint.setText("未配置 BILIBILI_COOKIES：请在「配置 → 内容订阅」填写登录 Cookie。")
            self._cookie_hint.show()

    def _apply_filters(self) -> None:
        if self._service is None:
            return
        self._timeline.set_subscription_filter(self._filter_subscription_id)

    def _on_subscription_selected(self, subscription_id: str) -> None:
        self._filter_subscription_id = subscription_id
        self._apply_filters()

    def _on_subscriptions_changed(self) -> None:
        self._filter_subscription_id = None
        self._subscriptions.refresh()
        self._apply_filters()

    def _on_sync(self) -> None:
        if self._service is None or self._sync_worker is not None:
            return
        if not self._service.cookies_configured():
            page_notify(self, "请先配置 BILIBILI_COOKIES", level="warning")
            return
        self._sync_btn.setEnabled(False)
        worker = FeedSyncWorker(self._service, self)
        self._sync_worker = worker
        worker.finished_with_result.connect(self._on_sync_finished)
        worker.start()

    def _on_sync_finished(self, result: object) -> None:
        worker = self._sync_worker
        self._sync_worker = None
        self._sync_btn.setEnabled(True)
        if worker is not None:
            release_thread(self._retired_workers, worker)
        message = getattr(result, "message", str(result))
        skipped = bool(getattr(result, "skipped", False))
        success = bool(getattr(result, "success", False))
        level = "info" if success or skipped else "error"
        page_notify(self, message, level=level)
        self._subscriptions.refresh()
        self._apply_filters()
        sync_info_feed_context(self.main_engine)

    def closeEvent(self, event) -> None:
        self.deactivate()
        super().closeEvent(event)
