"""多因子配方页 Worker 编排（配方试跑 / 雷达 / 龙头）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from vnpy_ashare.ai.context.screener import sync_screener_page_context
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.screener.data.screening_status import build_run_insight_detail
from vnpy_ashare.screener.run.run_diff import enrich_condition_run, enrich_recipe_run
from vnpy_ashare.screener.run.runner import ScreenerRunResult
from vnpy_ashare.ui.screener.workers.screener_workers import (
    LeaderScreenRunWorker,
    RadarResonanceRunWorker,
    ScreenerRecipeRunWorker,
)

if TYPE_CHECKING:
    from vnpy_ashare.ui.screener.pages.auto_screener_page import AutoScreenerPageWidget


class AutoScreenerRunController:
    """封装多因子配方页各类 RunWorker 的启动、取消与回调。"""

    _RUN_WORKER_ATTRS = (
        "_recipe_worker",
        "_radar_worker",
        "_leader_worker",
    )

    def __init__(self, page: AutoScreenerPageWidget) -> None:
        self._page = page
        self._recipe_worker: ScreenerRecipeRunWorker | None = None
        self._radar_worker: RadarResonanceRunWorker | None = None
        self._leader_worker: LeaderScreenRunWorker | None = None
        self._pending_leader_variant = "mainline"

    def run_recipe(self, recipe: Any, recipe_id: str) -> None:
        page = self._page
        if page._task_guard.active:
            return
        if self._recipe_worker is not None and self._recipe_worker.isRunning():
            return
        label = str(getattr(recipe, "name", recipe_id) or recipe_id)
        top_n = int(getattr(recipe, "top_n", 20) or 20)
        page._task_guard.begin(
            f"正在试跑配方「{label}」…",
            widgets=page._task_lock_widgets(),
            primary=page.recipe_panel._run_btn,
            primary_text="试跑配方",
            primary_handler=page.recipe_panel._run_recipe,
            on_cancel=self.cancel_runs,
        )
        page.run_output_panel.begin_run(label=label, top_n=top_n, kind="配方")
        worker = ScreenerRecipeRunWorker(recipe, recipe_id)
        self._recipe_worker = worker
        worker.finished.connect(self._on_recipe_finished)
        worker.failed.connect(self._on_recipe_failed)
        worker.start()

    def run_radar_resonance(self) -> None:
        page = self._page
        if page._task_guard.active:
            return
        if self._radar_worker is not None and self._radar_worker.isRunning():
            return
        top_n = int(page.recipe_panel._top_n_spin.value())
        page._task_guard.begin(
            "正在运行雷达共振选股…",
            widgets=page._task_lock_widgets(),
            primary=page.radar_resonance_btn,
            primary_text="雷达共振",
            primary_handler=self.run_radar_resonance,
            on_cancel=self.cancel_runs,
        )
        page.run_output_panel.begin_run(label="雷达共振", top_n=top_n, kind="雷达")
        worker = RadarResonanceRunWorker(page.main_engine, top_n=top_n, parent=page)
        self._radar_worker = worker
        worker.finished.connect(self._on_radar_finished)
        worker.failed.connect(self._on_radar_failed)
        worker.start()

    def run_leader_screen(self, *, variant: str = "mainline") -> None:
        page = self._page
        if page._task_guard.active:
            return
        if self._leader_worker is not None and self._leader_worker.isRunning():
            return
        top_n = int(page.recipe_panel._top_n_spin.value())
        self._pending_leader_variant = variant
        page._task_guard.begin(
            "正在运行雷达龙头选股…",
            widgets=page._task_lock_widgets(),
            primary=page.leader_screen_btn,
            primary_text="雷达龙头",
            primary_handler=lambda: self.run_leader_screen(variant=variant),
            on_cancel=self.cancel_runs,
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

    def cancel_runs(self) -> None:
        for attr in self._RUN_WORKER_ATTRS:
            worker = getattr(self, attr)
            if worker is not None:
                worker.request_cancel()

    def release_workers(self, *, timeout_ms: int = 0) -> None:
        page = self._page
        for attr in self._RUN_WORKER_ATTRS:
            worker = getattr(self, attr)
            setattr(self, attr, None)
            page._release_worker(worker, timeout_ms=timeout_ms)

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

    def _finalize_run(
        self,
        result: ScreenerRunResult,
        *,
        config: dict[str, Any],
        display_rows: list[ScreenerResultRow],
        detail_lines: list[str],
        success_message: str,
        persist: Callable[[], None] | None = None,
    ) -> None:
        page = self._page
        summary = page._result_presenter.apply_result(result, rows=display_rows, config=config)
        if persist is not None:
            persist()
        insight_detail = build_run_insight_detail(display_rows, config)
        lines = list(detail_lines)
        if insight_detail:
            lines.append(insight_detail)
        page.run_output_panel.complete_run(summary=summary, detail="\n".join(lines))
        page.run_sidebar.refresh()
        sync_screener_page_context(page.main_engine)
        page._toast.success(success_message)

    def _on_recipe_finished(self, result: ScreenerRunResult, recipe_id: str) -> None:
        def apply(result: ScreenerRunResult) -> None:
            config = {"trigger": "manual", "recipe_id": recipe_id}
            display_rows = enrich_recipe_run(list(result.rows), recipe_id, config)
            service = self._page._screening_service()

            def persist() -> None:
                if service is not None:
                    service.persist_run_result(result, extra_config=config)

            self._finalize_run(
                result,
                config=config,
                display_rows=display_rows,
                detail_lines=[f"配方 ID {recipe_id} · 已写入自动结果"],
                success_message=f"配方试跑完成，命中 {len(display_rows)} 条",
                persist=persist,
            )

        self._handle_run_finished(
            "_recipe_worker",
            result,
            cancel_toast="配方试跑已取消",
            apply=apply,
        )

    def _on_recipe_failed(self, message: str) -> None:
        self._handle_run_failed("_recipe_worker", message, cancel_toast="配方试跑已取消")

    def _on_radar_finished(self, result: ScreenerRunResult) -> None:
        def apply(result: ScreenerRunResult) -> None:
            config = {"trigger": "radar"}
            display_rows = enrich_condition_run(list(result.rows), result.condition, config, source=result.source)
            service = self._page._screening_service()

            def persist() -> None:
                if service is not None:
                    service.persist_run_result(result, trigger="radar", extra_config=config)

            self._finalize_run(
                result,
                config=config,
                display_rows=display_rows,
                detail_lines=["数据源 雷达共振 · 已写入历史运行"],
                success_message=f"雷达共振完成，命中 {len(result.rows)} 条",
                persist=persist,
            )

        self._handle_run_finished(
            "_radar_worker",
            result,
            cancel_toast="雷达共振选股已取消",
            apply=apply,
        )

    def _on_radar_failed(self, message: str) -> None:
        self._handle_run_failed("_radar_worker", message, cancel_toast="雷达共振选股已取消")

    def _on_leader_finished(self, result: ScreenerRunResult) -> None:
        def apply(result: ScreenerRunResult) -> None:
            config = {
                "trigger": "radar_leader",
                "leader_variant": self._pending_leader_variant,
            }
            display_rows = enrich_condition_run(list(result.rows), result.condition, config, source=result.source)
            service = self._page._screening_service()

            def persist() -> None:
                if service is not None:
                    service.persist_run_result(result, trigger="radar_leader", extra_config=config)

            self._finalize_run(
                result,
                config=config,
                display_rows=display_rows,
                detail_lines=["数据源 雷达龙头 · 已写入历史运行"],
                success_message=f"雷达龙头完成，命中 {len(result.rows)} 条",
                persist=persist,
            )

        self._handle_run_finished(
            "_leader_worker",
            result,
            cancel_toast="雷达龙头选股已取消",
            apply=apply,
        )

    def _on_leader_failed(self, message: str) -> None:
        self._handle_run_failed("_leader_worker", message, cancel_toast="雷达龙头选股已取消")
