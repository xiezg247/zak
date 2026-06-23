"""条件选股页结果展示与 AI 上下文同步。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnpy.event import Event

from vnpy_ashare.ai.context.screener import sync_screener_page_context
from vnpy_ashare.app.events import EVENT_ORB_ATTENTION, OrbAttentionRequest
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.screener.data.screening_status import build_run_insight_detail
from vnpy_ashare.screener.run.run_diff import enrich_condition_run
from vnpy_ashare.screener.run.runner import ScreenerRunResult
from vnpy_ashare.screener.run.ultra_short_pool_filter import filter_ultra_short_main_pool
from vnpy_ashare.ui.screener.widgets.screener_results_table import apply_screener_results_view

if TYPE_CHECKING:
    from vnpy_ashare.ui.screener.pages.screener_page import ScreenerPageWidget


class ScreenerResultPresenter:
    """选股结果表格、洞察面板与 ScreeningService 持久化。"""

    def __init__(self, page: ScreenerPageWidget) -> None:
        self._page = page

    def apply_screen_result(
        self,
        result: ScreenerRunResult,
        *,
        trigger: str = "manual",
        extra_config: dict[str, Any] | None = None,
    ) -> None:
        page = self._page
        config: dict[str, Any] = dict(extra_config or {})
        config["trigger"] = trigger
        page._last_run_config = dict(config)
        page._results = list(result.rows)
        if trigger in ("radar", "radar_leader", "industry", "pattern"):
            page._results = enrich_condition_run(
                page._results,
                result.condition,
                config,
                source=result.source,
            )
        service = page._screening_service()
        page._result_columns = result.columns or (service.resolve_export_columns(page._results) if service else [])
        self._refresh_table()
        if service is not None:
            if trigger == "manual":
                request, _ = page._build_request()
                service.save_manual_run(result, request)
            else:
                service.persist_run_result(result, extra_config=config)
        else:
            self._sync_context(
                condition=result.condition,
                rows=page._results,
                updated_at=result.updated_at,
            )
        updated = result.updated_at or "-"
        source_label = service.format_source_tag(result.source) if service else result.source
        summary = f"「{result.condition}」命中 {len(page._results)} 条 · 扫描 {result.total_scanned} 只 · {source_label} · 更新 {updated}"
        insight_detail = build_run_insight_detail(page._results, config if trigger != "manual" else None)
        detail_lines = [f"数据源 {result.source} · 已写入历史运行"]
        if insight_detail:
            detail_lines.append(insight_detail)
        page.result_insights.apply(page._results, config if trigger != "manual" else None)
        page.run_output_panel.complete_run(
            summary=summary,
            detail="\n".join(detail_lines),
        )
        page.run_sidebar.refresh()
        sync_screener_page_context(page.main_engine)
        page._toast.success(f"选股完成，命中 {len(page._results)} 条")
        if page.event_engine is not None:
            page.event_engine.put(
                Event(EVENT_ORB_ATTENTION, OrbAttentionRequest(source="screener")),
            )

    def load_historical_run(self, run_id: str) -> None:
        page = self._page
        service = page._screening_service()
        record = service.get_run_record(run_id) if service else None
        if record is None:
            page._append_action_log("历史运行不存在或已删除")
            self.clear_loaded_run_view()
            return
        page._loaded_run_id = run_id
        page._results = list(record.rows)
        page._result_columns = service.resolve_export_columns(page._results) if service else []
        self._refresh_table()
        self._sync_context(
            condition=record.condition,
            rows=page._results,
            updated_at=record.created_at,
        )
        source_label = service.format_source_tag(record.source) if service else record.source
        summary = f"[历史] 「{record.condition}」命中 {len(page._results)} 条 · 扫描 {record.total_scanned} · {source_label} · {record.created_at}"
        page.result_insights.apply(page._results, record.config)
        page.run_output_panel.load_history(summary=summary)
        sync_screener_page_context(page.main_engine)

    def filter_ultra_short_pool(self) -> None:
        page = self._page
        if not page._results:
            page._toast.info("暂无结果可筛选")
            return
        before = len(page._results)
        filtered = filter_ultra_short_main_pool(page._results)
        if not filtered:
            page._toast.warning("短线主池过滤后无命中（需连板/涨幅/龙头分 + 激进硬过滤）")
            return
        page._results = filtered
        self._refresh_table()
        page.result_insights.apply(page._results, page._last_run_config or None)
        sync_screener_page_context(page.main_engine)
        page._toast.success(f"已收窄至短线主池：{before} → {len(filtered)} 条")

    def clear_loaded_run_view(self) -> None:
        page = self._page
        page._loaded_run_id = None
        page._results = []
        page._result_columns = []
        self._refresh_table()
        self._sync_context(condition="", rows=[])
        page.result_insights.clear()

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
