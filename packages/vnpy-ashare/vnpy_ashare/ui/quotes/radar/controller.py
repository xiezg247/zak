"""雷达页控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.app.engine_access import get_watchlist_service
from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.quotes.radar_catalog import DEFAULT_SCREEN_TASK_VARIANT
from vnpy_ashare.ui.quotes.radar.worker import RadarBoardLoadWorker
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage
    from vnpy_ashare.ui.quotes.radar.card import RadarBoard


class RadarController(QtCore.QObject):
    def __init__(self, page: QuotesPage, board: RadarBoard) -> None:
        super().__init__(page)
        self._page = page
        self._board = board
        self._worker: RadarBoardLoadWorker | None = None
        self._retired_workers: list[QtCore.QThread] = []
        self._screen_task_variant = DEFAULT_SCREEN_TASK_VARIANT
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setInterval(page.config.quote_refresh_ms)
        self._refresh_timer.timeout.connect(self.refresh)

        board.variant_changed.connect(self._on_variant_changed)
        board.add_watchlist_requested.connect(self._on_add_watchlist)

    def activate(self) -> None:
        self.refresh()
        if self._page.config.auto_refresh_quotes:
            self._refresh_timer.start()

    def deactivate(self) -> None:
        self._refresh_timer.stop()
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.request_cancel()
        release_thread(self._retired_workers, worker, timeout_ms=0)

    def refresh(self) -> None:
        if thread_is_active(self._worker):
            return
        worker = RadarBoardLoadWorker(
            screen_task_variant=self._screen_task_variant,
            parent=self._page,
        )
        self._worker = worker
        worker.finished.connect(self._on_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda _payload: self._release_worker(worker))
        worker.failed.connect(lambda _msg: self._release_worker(worker))
        if hasattr(self._page, "status_label"):
            self._page.status_label.setText("雷达加载中…")
        worker.start()

    def _release_worker(self, worker: RadarBoardLoadWorker) -> None:
        if self._worker is worker:
            self._worker = None
        release_thread(self._retired_workers, worker)

    def _on_loaded(self, payload: dict) -> None:
        self._board.apply_board(payload)
        if hasattr(self._page, "status_label"):
            self._page.status_label.setText("就绪")

    def _on_failed(self, message: str) -> None:
        if hasattr(self._page, "status_label"):
            self._page.status_label.setText(f"雷达加载失败：{message}")
        page_notify(self._page, f"雷达加载失败：{message}", level="warning")

    def _on_variant_changed(self, card_id: str, variant_key: str) -> None:
        if card_id != "screen_task" or not variant_key:
            return
        self._screen_task_variant = variant_key
        self.refresh()

    def _on_add_watchlist(self, vt_symbol: str) -> None:
        service = get_watchlist_service(self._page._get_main_engine())
        if service is None:
            page_notify(self._page, "自选服务未就绪", level="warning")
            return
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            page_notify(self._page, f"无法解析合约：{vt_symbol}", level="warning")
            return
        if not service.add(item.symbol, item.exchange, item.name):
            reason = service.add_failure_reason(item.symbol, item.exchange)
            if reason == "full":
                page_notify(self._page, "自选池已满", level="warning")
            else:
                page_notify(self._page, f"已在自选池中：{vt_symbol}")
            return
        page_notify(self._page, f"已加入自选：{item.name or vt_symbol}")
