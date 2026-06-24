"""选股结果区勾选操作：自选、日 K 下载、回测、标杆对比。"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from vnpy.event import Event
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.app.engine_access import get_backtest_service
from vnpy_ashare.app.events import EVENT_OPEN_BACKTEST, BacktestRequest
from vnpy_ashare.screener.sentiment.recession_watchlist_guard import confirm_recession_batch_watchlist
from vnpy_ashare.ui.screener.dialogs.reference_peer_dialog import show_reference_peer_dialog
from vnpy_ashare.ui.screener.widgets.screener_results_table import iter_checked_table_rows
from vnpy_ashare.ui.screener.workers.screener_workers import ScreenerBatchDownloadWorker

if TYPE_CHECKING:
    from vnpy_ashare.ui.screener.pages.auto_screener_page import AutoScreenerPageWidget
    from vnpy_ashare.ui.screener.pages.screener_page import ScreenerPageWidget

    ScreenerResultsPage = ScreenerPageWidget | AutoScreenerPageWidget
else:
    ScreenerResultsPage = Any


class ScreenerSelectionController:
    """结果表格勾选行的批量操作。"""

    def __init__(self, page: ScreenerResultsPage) -> None:
        self._page = page

    def iter_checked_rows(self) -> list[dict[str, Any]]:
        return iter_checked_table_rows(self._page.result_table)

    def add_to_watchlist(self) -> None:
        page = self._page
        if page._watchlist_service is None:
            page._toast.warning("自选服务未就绪")
            return
        selected = self.iter_checked_rows()
        if not selected:
            page._toast.warning("请先勾选要加入自选的标的")
            return
        if not confirm_recession_batch_watchlist(page):
            return

        added = skipped = 0
        full_hit = False
        for row in selected:
            item = parse_stock_symbol(str(row.get("vt_symbol", "")))
            if item is None:
                skipped += 1
                continue
            name = str(row.get("name", "") or item.name)
            if page._watchlist_service.add(item.symbol, item.exchange, name):
                added += 1
            else:
                reason = page._watchlist_service.add_failure_reason(item.symbol, item.exchange)
                if reason == "full":
                    full_hit = True
                    break
                skipped += 1
        msg = f"新加入 {added} 只"
        if skipped:
            msg += f" · 跳过 {skipped} 只"
        if full_hit:
            msg += f" · 自选已满（最多 {page._watchlist_service.max_items} 只）"
        page._append_action_log(msg)
        page._toast.success(msg)

    def download_selected_bars(self) -> None:
        page = self._page
        if page._task_guard.active:
            return
        if page._download_worker is not None and page._download_worker.isRunning():
            return
        selected = self.iter_checked_rows()
        if not selected:
            page._toast.warning("请先勾选要下载日 K 的标的")
            return

        page._task_guard.begin(
            f"正在下载 {len(selected)} 只日 K…",
            widgets=page._task_lock_widgets(),
            primary=page.download_btn,
            primary_text="下载日K",
            primary_handler=self.download_selected_bars,
            on_cancel=self.cancel_download,
        )
        page._append_action_log(f"正在下载 {len(selected)} 只日 K…")
        worker = ScreenerBatchDownloadWorker(selected)
        page._download_worker = worker
        worker.finished.connect(self.on_download_finished)
        worker.failed.connect(self.on_download_failed)
        worker.start()

    def cancel_download(self) -> None:
        page = self._page
        if page._download_worker is not None:
            page._download_worker.request_cancel()

    def on_download_finished(self, result: Any) -> None:
        page = self._page
        worker = page._download_worker
        page._download_worker = None
        page._release_worker(worker)
        if not page._active:
            page._task_guard.end()
            return
        cancelled = page._task_guard.cancelled
        page._task_guard.end()
        message = getattr(result, "message", str(result))
        if cancelled or "已取消" in message:
            page._append_action_log("日 K 下载已取消")
            page._toast.info("日 K 下载已取消")
            return
        page._append_action_log(message)
        if getattr(result, "success", True):
            page._toast.success(message)
        else:
            page._toast.error(message)

    def on_download_failed(self, message: str) -> None:
        page = self._page
        worker = page._download_worker
        page._download_worker = None
        page._release_worker(worker)
        if not page._active:
            page._task_guard.end()
            return
        cancelled = page._task_guard.cancelled
        page._task_guard.end()
        if cancelled or message == "已取消":
            page._append_action_log("日 K 下载已取消")
            page._toast.info("日 K 下载已取消")
            return
        page._append_action_log(message)
        page._toast.error(message)

    def open_backtest_for_selection(self, *, source_page: str) -> None:
        page = self._page
        selected = self.iter_checked_rows()
        if not selected:
            page._toast.warning("请先勾选一只标的进行回测")
            return
        if len(selected) > 1:
            page._toast.info("「策略回测」仅打开单只；批量请用「批量回测」")
            return
        row = selected[0]
        vt_symbol = str(row.get("vt_symbol", ""))
        if not vt_symbol:
            page._toast.warning("缺少 vt_symbol")
            return
        name = str(row.get("name", ""))
        page.event_engine.put(
            Event(
                EVENT_OPEN_BACKTEST,
                BacktestRequest(
                    vt_symbol=vt_symbol,
                    source_page=source_page,
                    name=name,
                ),
            )
        )

    def run_batch_backtest(
        self,
        *,
        source_page: str,
        default_batch_source: str,
        radar_leader_batch_source: str = "batch_radar_leader",
        recipe_id_resolver: Callable[[], str | None] | None = None,
    ) -> None:
        page = self._page
        flow = page._batch_backtest_flow
        if flow is None or flow.is_running():
            return
        selected = self.iter_checked_rows()
        if not selected:
            page._toast.warning("请先勾选要批量回测的标的")
            return

        backtest_service = get_backtest_service(page.main_engine)
        strategies = backtest_service.list_strategies() if backtest_service else []
        class_names = [item["class_name"] for item in strategies if item.get("class_name")]
        trigger = str(page._last_run_config.get("trigger") or "")
        recipe_id = str(page._last_run_config.get("recipe_id") or "").strip() or None
        if recipe_id_resolver is not None and not recipe_id:
            recipe_id = recipe_id_resolver()
        batch_source = radar_leader_batch_source if trigger == "radar_leader" else default_batch_source
        flow.start(
            selected,
            source_page=source_page,
            batch_source=batch_source,
            list_strategies=lambda: class_names,
            on_running=lambda running: page.batch_backtest_btn.setDisabled(running),
            trigger=trigger or None,
            recipe_id=recipe_id,
        )

    def open_reference_peer(self) -> None:
        page = self._page
        selected = self.iter_checked_rows()
        if len(selected) != 1:
            page._toast.warning("请勾选恰好一只标的作为标杆")
            return
        row = selected[0]
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        if not vt_symbol:
            page._toast.warning("所选行缺少 vt_symbol")
            return
        name = str(row.get("name") or "")

        def watchlist_add(symbol: str, exchange, stock_name: str = "") -> bool:
            if page._watchlist_service is None:
                return False
            return page._watchlist_service.add(symbol, exchange, stock_name)

        show_reference_peer_dialog(
            vt_symbol=vt_symbol,
            reference_name=name,
            watchlist_add=watchlist_add if page._watchlist_service is not None else None,
            retired_workers=page._retired_workers,
            parent=page,
        )

    def export_csv(self, *, default_filename: str, empty_message: str) -> None:
        page = self._page
        if not page._results:
            page._toast.warning(empty_message)
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            page,
            "导出 CSV",
            default_filename,
            "CSV (*.csv)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        service = page._screening_service()
        if service is not None:
            service.export_csv(page._results, path)
        page._append_action_log(f"已导出：{path}")
        page._toast.success(f"已导出 CSV：{path}")
