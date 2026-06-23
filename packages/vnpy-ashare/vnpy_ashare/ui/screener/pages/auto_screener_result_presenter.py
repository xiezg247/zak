"""多因子配方页结果展示与 AI 上下文同步。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnpy_ashare.ai.context.screener import sync_screener_page_context
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.screener.run.runner import ScreenerRunResult
from vnpy_ashare.ui.screener.widgets.screener_results_table import apply_screener_results_view

if TYPE_CHECKING:
    from vnpy_ashare.ui.screener.pages.auto_screener_page import AutoScreenerPageWidget


class AutoScreenerResultPresenter:
    """配方试跑 / 自动结果表格、洞察面板与 ScreeningService 上下文。"""

    def __init__(self, page: AutoScreenerPageWidget) -> None:
        self._page = page

    def apply_result(
        self,
        result: ScreenerRunResult,
        *,
        prefix: str = "",
        rows: list[ScreenerResultRow] | None = None,
        config: dict[str, Any] | None = None,
    ) -> str:
        page = self._page
        service = page._screening_service()
        page._results = list(rows if rows is not None else result.rows)
        if config is not None:
            page._last_run_config = dict(config)
        page._result_columns = result.columns or (service.resolve_export_columns(page._results) if service else [])
        self._refresh_table()
        self._sync_context(
            condition=result.condition,
            rows=page._results,
            updated_at=result.updated_at,
        )
        page.result_insights.apply(page._results, config)
        return self.format_result_summary(
            condition=result.condition,
            row_count=len(page._results),
            total_scanned=result.total_scanned,
            source=result.source,
            updated_at=result.updated_at,
            prefix=prefix,
        )

    def load_historical_run(self, run_id: str, *, from_scheduler: bool = False) -> None:
        page = self._page
        service = page._screening_service()
        record = service.get_run_record(run_id) if service else None
        if record is None:
            page._append_action_log("配方结果不存在或已删除")
            self.clear_loaded_run_view()
            return
        page._loaded_run_id = run_id
        if service is not None:
            service.mark_run_read(run_id)
        page._results = list(record.rows)
        page._result_columns = service.resolve_export_columns(page._results) if service else []
        self._refresh_table()
        self._sync_context(
            condition=record.condition,
            rows=page._results,
            updated_at=record.created_at,
        )
        trigger = str(record.config.get("trigger", ""))
        prefix = ""
        if trigger.startswith("scheduled_"):
            reason = record.config.get("reason_summary") or trigger.removeprefix("scheduled_")
            prefix = f"自动 · {reason} · "
        elif record.config.get("recipe_id"):
            prefix = "配方试跑 · "
        summary = self.format_result_summary(
            condition=record.condition,
            row_count=len(page._results),
            total_scanned=record.total_scanned,
            source=record.source,
            updated_at=record.created_at,
            prefix=prefix,
        )
        log_tag = "定时" if from_scheduler else "历史"
        page.result_insights.apply(page._results, record.config)
        page.run_output_panel.load_history(summary=summary, log_tag=log_tag)
        page.run_sidebar.refresh()
        sync_screener_page_context(page.main_engine)

    def clear_loaded_run_view(self) -> None:
        page = self._page
        page._loaded_run_id = None
        page._results = []
        page._result_columns = []
        self._refresh_table()
        self._sync_context(condition="", rows=[])
        page.result_insights.clear()

    def format_result_summary(
        self,
        *,
        condition: str,
        row_count: int,
        total_scanned: int,
        source: str,
        updated_at: str | None,
        prefix: str = "",
    ) -> str:
        service = self._page._screening_service()
        source_label = service.format_source_tag(source) if service else source
        updated = updated_at or "-"
        headline = f"「{condition}」命中 {row_count} 条 · 扫描 {total_scanned} 只 · {source_label} · 更新 {updated}"
        return f"{prefix}{headline}" if prefix else headline

    def _refresh_table(self) -> None:
        page = self._page
        apply_screener_results_view(
            page.result_table,
            page._results,
            page._result_columns,
            empty_label=page._empty_result_label,
            select_all_btn=page.select_all_btn,
            result_action_bar=page.result_action_bar,
            export_btn=page.export_btn,
        )

    def _sync_context(
        self,
        *,
        condition: str,
        rows: list[ScreenerResultRow],
        updated_at: str | None = None,
    ) -> None:
        service = self._page._screening_service()
        if service is not None:
            service.set_screening_results(
                condition=condition,
                rows=rows,
                updated_at=updated_at,
            )
