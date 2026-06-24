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
    unread_changed = QtCore.Signal()

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine | None) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("InfoFeedPage")

        self._service = get_feed_service(main_engine)
        self._sync_worker: FeedSyncWorker | None = None
        self._retired_workers: list[QtCore.QThread] = []
        self._filter_subscription_id: str | None = None

        self._unread_label = QtWidgets.QLabel("未读 0", self)
        self._filter_combo = QtWidgets.QComboBox(self)
        self._filter_combo.addItem("全部", "all")
        self._filter_combo.addItem("仅未读", "unread")
        self._mark_all_btn = QtWidgets.QPushButton("全部已读", self)
        self._sync_btn = QtWidgets.QPushButton("立即同步", self)
        self._cookie_hint = QtWidgets.QLabel("", self)
        self._cookie_hint.setObjectName("InfoFeedCookieHint")

        top = QtWidgets.QHBoxLayout()
        top.addWidget(section_title("信息流"))
        top.addStretch()
        top.addWidget(self._unread_label)
        top.addWidget(self._filter_combo)
        top.addWidget(self._mark_all_btn)
        top.addWidget(self._sync_btn)

        if self._service is None:
            body = QtWidgets.QLabel("A 股引擎未加载，无法使用信息流。", self)
            layout = QtWidgets.QVBoxLayout(self)
            layout.addLayout(top)
            layout.addWidget(body, stretch=1)
            self._toast = PageToastHost(self)
            layout.addWidget(self._toast)
            return

        self._timeline = FeedTimelineView(self._service, event_engine, self)
        self._subscriptions = SubscriptionPanel(self._service, self)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._timeline)
        splitter.addWidget(self._subscriptions)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([720, 280])

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)
        layout.addLayout(top)
        layout.addWidget(self._cookie_hint)
        layout.addWidget(splitter, stretch=1)
        self._toast = PageToastHost(self)
        layout.addWidget(self._toast)

        self._filter_combo.currentIndexChanged.connect(self._apply_filters)
        self._mark_all_btn.clicked.connect(self._on_mark_all_read)
        self._sync_btn.clicked.connect(self._on_sync)
        self._timeline.unread_changed.connect(self._refresh_unread_badge)
        self._subscriptions.selection_changed.connect(self._on_subscription_selected)
        self._subscriptions.subscriptions_changed.connect(self._on_subscriptions_changed)

    def activate(self) -> None:
        if self._service is None:
            return
        sync_info_feed_context(self.main_engine)
        self._refresh_cookie_hint()
        self._subscriptions.refresh()
        self._apply_filters()
        self._refresh_unread_badge()

    def deactivate(self) -> None:
        worker = self._sync_worker
        self._sync_worker = None
        if worker is not None:
            release_thread(self._retired_workers, worker)

    def unread_count(self) -> int:
        if self._service is None:
            return 0
        return self._service.count_unread()

    def _refresh_cookie_hint(self) -> None:
        if self._service is None:
            return
        if self._service.cookies_configured():
            self._cookie_hint.setText("")
        else:
            self._cookie_hint.setText("未配置 BILIBILI_COOKIES：请在「配置 → 内容订阅」填写登录 Cookie。")

    def _apply_filters(self) -> None:
        if self._service is None:
            return
        mode = str(self._filter_combo.currentData())
        self._timeline.set_filters(
            unread_only=mode == "unread",
            subscription_id=self._filter_subscription_id,
        )
        self._refresh_unread_badge()

    def _on_subscription_selected(self, subscription_id: str) -> None:
        self._filter_subscription_id = subscription_id
        self._apply_filters()

    def _on_subscriptions_changed(self) -> None:
        self._filter_subscription_id = None
        self._subscriptions.refresh()
        self._apply_filters()

    def _on_mark_all_read(self) -> None:
        if self._service is None:
            return
        self._service.mark_all_read(subscription_id=self._filter_subscription_id)
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

    def _refresh_unread_badge(self) -> None:
        count = self.unread_count()
        self._unread_label.setText(f"未读 {count}")
        self.unread_changed.emit()

    def closeEvent(self, event) -> None:
        self.deactivate()
        super().closeEvent(event)
