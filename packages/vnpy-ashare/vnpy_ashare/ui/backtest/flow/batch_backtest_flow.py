"""批量回测共用流程（选股 / 自选）。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from vnpy.event import Event
from vnpy.trader.constant import Interval
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.app.engine_access import get_service
from vnpy_ashare.app.events import EVENT_OPEN_BATCH_BACKTEST, BatchBacktestViewRequest
from vnpy_ashare.backtest.batch_templates import (
    apply_batch_backtest_template,
    batch_backtest_template_note,
    resolve_batch_backtest_template_id,
)
from vnpy_ashare.jobs.bars.focus_pool_minute import summarize_minute_gaps_for_vt_symbols
from vnpy_ashare.screener.batch.batch_actions import (
    BatchBacktestParams,
    load_batch_backtest_defaults,
    persist_batch_backtest_results,
)
from vnpy_ashare.ui.backtest.workers.focus_pool_minute_worker import FocusPoolMinuteFillWorker
from vnpy_ashare.ui.screener.dialogs.screener_batch_dialog import ScreenerBatchBacktestConfigDialog
from vnpy_ashare.ui.screener.workers.screener_workers import ScreenerBatchBacktestWorker
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import release_thread


class BatchBacktestFlow:
    """配置对话框 → 后台 Worker → 落库 → 打开回测对比页。"""

    def __init__(
        self,
        *,
        main_engine: Any,
        event_engine: Any,
        parent: QtWidgets.QWidget,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.parent = parent
        self._on_status = on_status or (lambda _msg: None)
        self._worker: ScreenerBatchBacktestWorker | None = None
        self._minute_worker: FocusPoolMinuteFillWorker | None = None
        self._retired_workers: list[QtCore.QThread] = []
        self._last_params: BatchBacktestParams | None = None
        self._batch_source = "batch_screener"
        self._source_page = ""

    def is_running(self) -> bool:
        if self._worker is not None and self._worker.isRunning():
            return True
        minute = self._minute_worker
        return minute is not None and minute.isRunning()

    def release_worker(
        self,
        retired: list[QtCore.QThread],
        *,
        timeout_ms: int = 3000,
    ) -> None:
        worker = self._worker
        self._worker = None
        release_thread(retired, worker, timeout_ms=timeout_ms)
        minute = self._minute_worker
        self._minute_worker = None
        release_thread(retired, minute, timeout_ms=0)
        for pending in list(self._retired_workers):
            release_thread(retired, pending, timeout_ms=0)
        self._retired_workers.clear()

    def start(
        self,
        rows: list[dict[str, Any]],
        *,
        source_page: str,
        batch_source: str = "batch_screener",
        list_strategies: Callable[[], list[str]] | None = None,
        on_running: Callable[[bool], None] | None = None,
        default_class_name: str | None = None,
        default_strategy_setting: dict[str, Any] | None = None,
        profile_id: str | None = None,
        recipe_id: str | None = None,
        trigger: str | None = None,
    ) -> None:
        if self.is_running():
            return
        if not rows:
            page_notify(self.parent, "没有可批量回测的标的")
            return
        if self.main_engine is None:
            page_notify(self.parent, "主引擎未就绪", level="warning", title="批量回测")
            return
        if self.event_engine is None:
            page_notify(self.parent, "事件引擎未就绪", level="warning", title="批量回测")
            return

        strategies = list_strategies() if list_strategies is not None else self._default_strategies()
        defaults = load_batch_backtest_defaults()
        has_class_override = default_class_name is not None
        has_setting_override = default_strategy_setting is not None
        defaults = apply_batch_backtest_template(
            defaults,
            profile_id=profile_id,
            recipe_id=recipe_id,
            trigger=trigger,
            override_class_name=not has_class_override,
            override_dates=True,
            override_setting=not has_setting_override,
        )
        class_default = (default_class_name or defaults.class_name).strip() or defaults.class_name
        merged_setting = default_strategy_setting if has_setting_override else defaults.strategy_setting
        auto_template_id = resolve_batch_backtest_template_id(
            profile_id=profile_id,
            recipe_id=recipe_id,
            trigger=trigger,
        )
        template_note = batch_backtest_template_note(
            profile_id=profile_id,
            recipe_id=recipe_id,
            trigger=trigger,
        )
        dialog = ScreenerBatchBacktestConfigDialog(
            class_names=strategies,
            default_class=class_default,
            default_start=defaults.start.strftime("%Y-%m-%d"),
            default_end=defaults.end.strftime("%Y-%m-%d"),
            count=len(rows),
            template_note=template_note,
            auto_template_id=auto_template_id,
            parent=self.parent,
        )
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        try:
            start = datetime.strptime(dialog.start_text[:10], "%Y-%m-%d")
            end = datetime.strptime(dialog.end_text[:10], "%Y-%m-%d")
        except ValueError:
            page_notify(self.parent, "日期格式应为 YYYY-MM-DD", level="warning")
            return

        base = BatchBacktestParams(
            class_name=dialog.class_name,
            start=start,
            end=end,
            rate=defaults.rate,
            slippage=defaults.slippage,
            size=defaults.size,
            pricetick=defaults.pricetick,
            capital=defaults.capital,
            strategy_setting=merged_setting,
            interval=defaults.interval,
        )
        selected_template_id = (dialog.template_id or "").strip() or None
        if selected_template_id:
            params = apply_batch_backtest_template(
                base,
                template_id=selected_template_id,
                override_class_name=False,
                override_dates=False,
                override_setting=True,
            )
        else:
            params = apply_batch_backtest_template(
                base,
                profile_id=profile_id,
                recipe_id=recipe_id,
                trigger=trigger,
                override_class_name=False,
                override_dates=False,
                override_setting=not has_setting_override,
            )
            if has_setting_override:
                params = params.model_copy(update={"strategy_setting": merged_setting})

        self._last_params = params
        self._batch_source = batch_source
        if trigger == "radar_leader":
            self._batch_source = "batch_radar_leader"
        self._source_page = source_page
        if on_running is not None:
            on_running(True)
        self._maybe_start_with_minute_precheck(rows, params, on_running)

    def _maybe_start_with_minute_precheck(
        self,
        rows: list[dict[str, Any]],
        params: BatchBacktestParams,
        on_running: Callable[[bool], None] | None,
    ) -> None:
        if params.interval != Interval.MINUTE:
            self._launch_batch_worker(rows, params, on_running)
            return

        vt_symbols = [str(row.get("vt_symbol") or "").strip() for row in rows]
        vt_symbols = [symbol for symbol in vt_symbols if symbol]
        summary = summarize_minute_gaps_for_vt_symbols(vt_symbols)
        if summary.needs_fill == 0:
            self._launch_batch_worker(rows, params, on_running)
            return

        reply = QtWidgets.QMessageBox.question(
            self.parent,
            "分 K 数据预检",
            f"{summary.needs_fill}/{summary.total} 只缺少或未更新本地 1 分钟 K 线。\n"
            "是否先自动补全再回测？（需 Tushare，耗时视数量而定）",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No
            | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Yes,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Cancel:
            if on_running is not None:
                on_running(False)
            return
        if reply == QtWidgets.QMessageBox.StandardButton.No:
            self._launch_batch_worker(rows, params, on_running)
            return

        self._on_status(f"补全 1m K（{summary.needs_fill} 只）…")
        minute_worker = FocusPoolMinuteFillWorker(vt_symbols)
        self._minute_worker = minute_worker
        minute_worker.log.connect(self._on_status)
        minute_worker.finished.connect(lambda _result: self._launch_batch_worker(rows, params, on_running))
        minute_worker.failed.connect(
            lambda message: self._on_minute_fill_failed(message, rows, params, on_running),
        )
        minute_worker.start()

    def _on_minute_fill_failed(
        self,
        message: str,
        rows: list[dict[str, Any]],
        params: BatchBacktestParams,
        on_running: Callable[[bool], None] | None,
    ) -> None:
        self._minute_worker = None
        reply = QtWidgets.QMessageBox.question(
            self.parent,
            "1m K 补全失败",
            f"{message}\n是否仍继续批量回测？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            if on_running is not None:
                on_running(False)
            self._on_status("已取消批量回测")
            return
        self._launch_batch_worker(rows, params, on_running)

    def _launch_batch_worker(
        self,
        rows: list[dict[str, Any]],
        params: BatchBacktestParams,
        on_running: Callable[[bool], None] | None,
    ) -> None:
        self._minute_worker = None
        self._on_status(f"批量回测中（{len(rows)} 只）…")

        worker = ScreenerBatchBacktestWorker(
            self.main_engine,
            rows,
            params,
        )
        self._worker = worker
        worker.finished.connect(lambda result: self._on_finished(result, on_running))
        worker.failed.connect(lambda message: self._on_failed(message, on_running))
        worker.start()

    def _release_worker(self, worker: ScreenerBatchBacktestWorker | None) -> None:
        release_thread(self._retired_workers, worker)

    def _default_strategies(self) -> list[str]:
        service = get_service(self.main_engine, "backtest_service")
        if service is None:
            return []
        return [item["class_name"] for item in service.list_strategies() if item.get("class_name")]

    def _on_finished(
        self,
        rows: object,
        on_running: Callable[[bool], None] | None,
    ) -> None:
        worker = self._worker
        self._worker = None
        self._release_worker(worker)
        if on_running is not None:
            on_running(False)
        result_rows = list(rows) if isinstance(rows, list) else []
        batch_id = None
        if self._last_params is not None and result_rows:
            batch_id = persist_batch_backtest_results(
                self._last_params,
                result_rows,
                source=self._batch_source,
            )
        if batch_id and self.event_engine is not None:
            self._on_status(f"批量回测完成：{len(result_rows)} 只 · 已打开回测对比页")
            self.event_engine.put(
                Event(
                    EVENT_OPEN_BATCH_BACKTEST,
                    BatchBacktestViewRequest(
                        batch_id=batch_id,
                        source_page=self._source_page,
                    ),
                )
            )
        else:
            self._on_status(f"批量回测完成：{len(result_rows)} 只")

    def _on_failed(
        self,
        message: str,
        on_running: Callable[[bool], None] | None,
    ) -> None:
        worker = self._worker
        self._worker = None
        self._release_worker(worker)
        if on_running is not None:
            on_running(False)
        self._on_status(message)
        page_notify(self.parent, message, level="warning", title="批量回测")
