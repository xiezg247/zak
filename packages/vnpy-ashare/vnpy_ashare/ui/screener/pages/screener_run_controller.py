"""条件选股页 Worker 编排（条件 / 形态 / 雷达 / 龙头 / 行业）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from vnpy_ashare.screener.run.runner import ScreenerRunResult
from vnpy_ashare.ui.screener.workers.screener_workers import (
    IndustryScreenRunWorker,
    LeaderScreenRunWorker,
    PatternScreenRunWorker,
    RadarResonanceRunWorker,
    ScreenerRunWorker,
)

if TYPE_CHECKING:
    from vnpy_ashare.ui.screener.pages.screener_page import ScreenerPageWidget


class ScreenerRunController:
    """封装选股页各类 RunWorker 的启动、取消与回调。"""

    _SCREENING_WORKER_ATTRS = (
        "_worker",
        "_pattern_worker",
        "_radar_worker",
        "_leader_worker",
        "_industry_worker",
    )

    def __init__(self, page: ScreenerPageWidget) -> None:
        self._page = page
        self._worker: ScreenerRunWorker | None = None
        self._pattern_worker: PatternScreenRunWorker | None = None
        self._radar_worker: RadarResonanceRunWorker | None = None
        self._leader_worker: LeaderScreenRunWorker | None = None
        self._industry_worker: IndustryScreenRunWorker | None = None
        self._pending_leader_variant = "mainline"

    @property
    def pending_leader_variant(self) -> str:
        return self._pending_leader_variant

    def run_screening(self) -> None:
        page = self._page
        if page._task_guard.active:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        request, _ = page._build_request()
        if request is None:
            return

        page._task_guard.begin(
            "正在运行条件选股…",
            widgets=page._task_lock_widgets(),
            primary=page.run_btn,
            primary_text="▶  运行条件选股",
            primary_handler=self.run_screening,
            on_cancel=self.cancel_screening,
        )
        page.run_output_panel.begin_run(
            label=page.preset_combo.currentText(),
            top_n=page.top_n_spin.value(),
        )

        worker = ScreenerRunWorker(
            preset=request.preset,
            top_n=request.top_n,
            min_change_pct=request.min_change_pct,
            max_change_pct=request.max_change_pct,
            min_turnover=request.min_turnover,
            scheme_id=request.scheme_id,
        )
        if request.scheme_id:
            worker.preset = page.preset_combo.currentText()
        self._worker = worker
        worker.finished.connect(self._on_screen_finished)
        worker.failed.connect(self._on_screen_failed)
        worker.start()

    def cancel_screening(self) -> None:
        for attr in self._SCREENING_WORKER_ATTRS:
            worker = getattr(self, attr)
            if worker is not None:
                worker.request_cancel()

    def release_workers(self, *, timeout_ms: int = 0) -> None:
        page = self._page
        for attr in self._SCREENING_WORKER_ATTRS:
            worker = getattr(self, attr)
            setattr(self, attr, None)
            page._release_worker(worker, timeout_ms=timeout_ms)

    def run_leader_screen(self, *, variant: str = "mainline") -> None:
        page = self._page
        if page._task_guard.active:
            return
        if self._leader_worker is not None and self._leader_worker.isRunning():
            return
        top_n = page.top_n_spin.value()
        self._pending_leader_variant = variant
        page._task_guard.begin(
            "正在运行雷达龙头选股…",
            widgets=page._task_lock_widgets(),
            primary=page.leader_screen_btn,
            primary_text="运行雷达龙头",
            primary_handler=lambda: self.run_leader_screen(variant=variant),
            on_cancel=self.cancel_screening,
        )
        page.run_output_panel.begin_run(label="雷达龙头", top_n=top_n, kind="雷达")
        worker = LeaderScreenRunWorker(
            page.main_engine,
            top_n=top_n,
            variant=variant,
            parent=page,
        )
        self._leader_worker = worker
        worker.finished.connect(self._on_leader_finished)
        worker.failed.connect(self._on_leader_failed)
        worker.start()

    def run_radar_resonance(self) -> None:
        page = self._page
        if page._task_guard.active:
            return
        if self._radar_worker is not None and self._radar_worker.isRunning():
            return
        top_n = page.top_n_spin.value()
        page._task_guard.begin(
            "正在运行雷达共振选股…",
            widgets=page._task_lock_widgets(),
            primary=page.radar_resonance_btn,
            primary_text="运行雷达共振",
            primary_handler=self.run_radar_resonance,
            on_cancel=self.cancel_screening,
        )
        page.run_output_panel.begin_run(label="雷达共振", top_n=top_n, kind="雷达")
        worker = RadarResonanceRunWorker(
            page.main_engine,
            top_n=top_n,
            parent=page,
        )
        self._radar_worker = worker
        worker.finished.connect(self._on_radar_finished)
        worker.failed.connect(self._on_radar_failed)
        worker.start()

    def run_industry_from_form(self) -> None:
        page = self._page
        industry = page.industry_edit.text().strip()
        if not industry:
            page._toast.warning("请输入行业名称")
            return
        page._pending_industry = industry
        self.run_industry_screen()

    def run_industry_screen(self) -> None:
        page = self._page
        industry = page._pending_industry.strip()
        if not industry:
            page._toast.warning("请先选择行业")
            return
        if page._task_guard.active:
            return
        if self._industry_worker is not None and self._industry_worker.isRunning():
            return
        top_n = page.top_n_spin.value()
        page._task_guard.begin(
            f"正在筛选「{industry}」成分股…",
            widgets=page._task_lock_widgets(),
            primary=None,
            on_cancel=self.cancel_screening,
        )
        page.run_output_panel.begin_run(label=f"{industry} 成分", top_n=top_n, kind="行业")
        worker = IndustryScreenRunWorker(
            page.main_engine,
            industry=industry,
            top_n=top_n,
            parent=page,
        )
        self._industry_worker = worker
        worker.finished.connect(self._on_industry_finished)
        worker.failed.connect(self._on_industry_failed)
        worker.start()

    def run_pattern_screen(self) -> None:
        page = self._page
        if page._task_guard.active:
            return
        if self._pattern_worker is not None and self._pattern_worker.isRunning():
            return
        pattern = page.pattern_combo.currentText().strip()
        if not pattern:
            return
        top_n = page.top_n_spin.value()
        page._task_guard.begin(
            f"正在运行形态选股「{pattern}」…",
            widgets=page._task_lock_widgets(),
            primary=page.pattern_run_btn,
            primary_text="运行形态选股",
            primary_handler=self.run_pattern_screen,
            on_cancel=self.cancel_screening,
        )
        page.run_output_panel.begin_run(label=pattern, top_n=top_n, kind="形态")
        worker = PatternScreenRunWorker(
            page.main_engine,
            pattern=pattern,
            top_n=top_n,
            parent=page,
        )
        self._pattern_worker = worker
        worker.finished.connect(self._on_pattern_finished)
        worker.failed.connect(self._on_pattern_failed)
        worker.start()

    def _pop_worker(self, attr: str) -> Any | None:
        worker = getattr(self, attr)
        setattr(self, attr, None)
        return worker

    def _handle_run_finished(
        self,
        worker_attr: str,
        result: ScreenerRunResult,
        *,
        cancel_toast: str,
        apply: Callable[[ScreenerRunResult], None],
    ) -> None:
        worker = self._pop_worker(worker_attr)
        page = self._page
        page._release_worker(worker)
        if not page._active:
            page._task_guard.end()
            return
        cancelled = page._task_guard.cancelled
        page._task_guard.end()
        if cancelled:
            page.run_output_panel.fail_run("已取消")
            page._toast.info(cancel_toast)
            return
        apply(result)

    def _handle_run_failed(
        self,
        worker_attr: str,
        message: str,
        *,
        cancel_toast: str,
    ) -> None:
        worker = self._pop_worker(worker_attr)
        page = self._page
        page._release_worker(worker)
        if not page._active:
            page._task_guard.end()
            return
        cancelled = page._task_guard.cancelled
        page._task_guard.end()
        if cancelled or message == "已取消":
            page.run_output_panel.fail_run("已取消")
            page._toast.info(cancel_toast)
            return
        page.run_output_panel.fail_run(message)
        page._toast.error(message)

    def _on_screen_finished(self, result: ScreenerRunResult) -> None:
        self._handle_run_finished(
            "_worker",
            result,
            cancel_toast="条件选股已取消",
            apply=lambda item: self._page._apply_screen_result(item, trigger="manual"),
        )

    def _on_screen_failed(self, message: str) -> None:
        worker = self._pop_worker("_worker")
        page = self._page
        page._release_worker(worker)
        if not page._active:
            page._task_guard.end()
            return
        cancelled = page._task_guard.cancelled
        page._task_guard.end()
        if cancelled or message == "已取消":
            page.run_output_panel.fail_run("已取消")
            page._toast.info("条件选股已取消")
            return
        page.run_output_panel.fail_run(message)
        if message != "已取消":
            page._toast.error(message)

    def _on_leader_finished(self, result: ScreenerRunResult) -> None:
        def apply(result: ScreenerRunResult) -> None:
            config = {
                "trigger": "radar_leader",
                "leader_variant": self._pending_leader_variant,
            }
            self._page._apply_screen_result(result, trigger="radar_leader", extra_config=config)

        self._handle_run_finished(
            "_leader_worker",
            result,
            cancel_toast="雷达龙头选股已取消",
            apply=apply,
        )

    def _on_leader_failed(self, message: str) -> None:
        self._handle_run_failed("_leader_worker", message, cancel_toast="雷达龙头选股已取消")

    def _on_radar_finished(self, result: ScreenerRunResult) -> None:
        self._handle_run_finished(
            "_radar_worker",
            result,
            cancel_toast="雷达共振选股已取消",
            apply=lambda item: self._page._apply_screen_result(item, trigger="radar"),
        )

    def _on_radar_failed(self, message: str) -> None:
        self._handle_run_failed("_radar_worker", message, cancel_toast="雷达共振选股已取消")

    def _on_industry_finished(self, result: ScreenerRunResult) -> None:
        def apply(result: ScreenerRunResult) -> None:
            industry = self._page._pending_industry.strip()
            self._page._apply_screen_result(
                result,
                trigger="industry",
                extra_config={"industry": industry} if industry else None,
            )

        self._handle_run_finished(
            "_industry_worker",
            result,
            cancel_toast="行业成分选股已取消",
            apply=apply,
        )

    def _on_industry_failed(self, message: str) -> None:
        self._handle_run_failed("_industry_worker", message, cancel_toast="行业成分选股已取消")

    def _on_pattern_finished(self, result: ScreenerRunResult) -> None:
        def apply(result: ScreenerRunResult) -> None:
            self._page._apply_screen_result(
                result,
                trigger="pattern",
                extra_config={"pattern": self._page.pattern_combo.currentText().strip()},
            )

        self._handle_run_finished(
            "_pattern_worker",
            result,
            cancel_toast="形态选股已取消",
            apply=apply,
        )

    def _on_pattern_failed(self, message: str) -> None:
        self._handle_run_failed("_pattern_worker", message, cancel_toast="形态选股已取消")
