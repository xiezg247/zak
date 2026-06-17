"""自选页批量回测。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.config.preferences.strategy_profile import load_strategy_profile_id
from vnpy_ashare.screener.batch.batch_actions import (
    stock_items_to_batch_rows,
    watchlist_items_to_rows,
)
from vnpy_ashare.ui.backtest import BatchBacktestFlow
from vnpy_ashare.ui.quotes.page.run_log import append_run_log, begin_run_log, complete_run_log, fail_run_log

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class WatchlistBatchBacktestController:
    """从自选池发起批量回测。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page
        self._flow: BatchBacktestFlow | None = None

    def _on_flow_status(self, message: str) -> None:
        page = self._page
        page.status_label.setText(message)
        if not page.config.show_run_output_panel:
            return
        if message.startswith("批量回测完成"):
            complete_run_log(page, message)
        elif "失败" in message or message.startswith("批量回测失败"):
            fail_run_log(page, message)
        else:
            append_run_log(page, message)

    def _get_flow(self) -> BatchBacktestFlow:
        if self._flow is None:
            page = self._page
            self._flow = BatchBacktestFlow(
                main_engine=page._get_main_engine(),
                event_engine=page.event_engine,
                parent=page,
                on_status=self._on_flow_status,
            )
        return self._flow

    def release_workers(self, retired: list[QtCore.QThread]) -> None:
        if self._flow is not None:
            self._flow.release_worker(retired, timeout_ms=0)

    def _watchlist_pool_empty(self) -> bool:
        page = self._page
        service = page._get_watchlist_service()
        if service is not None and service.get_items():
            return False
        return not (page.page_name == "自选" and page.all_stocks)

    def collect_watchlist_rows(self) -> list[dict[str, str]]:
        page = self._page
        if page.page_name == "自选":
            selected = page._table.selected_items()
            if selected:
                return stock_items_to_batch_rows(selected)
            return []
        service = page._get_watchlist_service()
        if service is not None:
            items = service.get_items()
            if items:
                return watchlist_items_to_rows(items)
        return []

    def update_action_buttons(self) -> None:
        page = self._page
        if not page.config.show_batch_backtest_button:
            return
        button = page.batch_backtest_button
        running = self._flow is not None and self._flow.is_running()
        pool_empty = self._watchlist_pool_empty()
        has_selection = bool(page._table.selected_items()) if page.page_name == "自选" else bool(self.collect_watchlist_rows())
        button.setEnabled(not running and not pool_empty and has_selection)

    def run_batch_backtest(self) -> None:
        if self._watchlist_pool_empty():
            self._page._toast.warning("自选池为空，请先添加标的")
            return
        rows = self.collect_watchlist_rows()
        if not rows:
            self._page._toast.warning("请先在自选表中选择要批量回测的标的")
            return
        begin_run_log(self._page, f"批量回测 · {len(rows)} 只")
        flow = self._get_flow()
        signal_config = self._page.signal_config.normalized()
        flow.start(
            rows,
            source_page="自选",
            batch_source="batch_watchlist",
            default_class_name=signal_config.class_name,
            default_strategy_setting=signal_config.to_strategy_setting(),
            profile_id=load_strategy_profile_id(),
            on_running=lambda running: self._page.batch_backtest_button.setDisabled(running),
        )
