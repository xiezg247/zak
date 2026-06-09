"""选股 Service（委托 screener.runner）。

AI 上下文链路::

    选股完成 → persist_run_result / persist_scheduled_recipe_run
            → context_store.set_screening_results
            → publish_screener_page_context（enrich 悬浮球 actions）

UI 读写历史/方案/导出请走本类 Facade，勿直连 ``screener/run_store``。
"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context import AiContextData
from vnpy_ashare.ai.context_store import (
    ScreeningResultContext,
    set_ai_context,
)
from vnpy_ashare.ai.context_store import (
    get_screening_results as _get_screening_results,
)
from vnpy_ashare.ai.context_store import (
    set_screening_results as _set_screening_results,
)
from vnpy_ashare.screener.presets import list_builtin_preset_names
from vnpy_ashare.screener.runner import ScreenerRequest, ScreenerRunResult, run_screener
from vnpy_ashare.services.base import BaseService

AVAILABLE_SCREENERS = list_builtin_preset_names()


class ScreeningService(BaseService):
    """执行选股条件，返回候选标的。"""

    def list_screeners(self) -> list[str]:
        from vnpy_ashare.screener.runner import list_all_preset_names

        return list_all_preset_names(include_saved=True)

    def list_quote_screeners(self) -> list[str]:
        from vnpy_ashare.screener.presets import list_quote_preset_names

        return list_quote_preset_names()

    def list_tushare_screeners(self) -> list[str]:
        from vnpy_ashare.screener.presets import list_tushare_preset_names

        return list_tushare_preset_names()

    def load_quote_rows(self) -> tuple[list[dict[str, Any]] | None, str | None]:
        """加载行情行：优先 QuoteService 缓存，其次 Redis 全市场快照。"""
        quote_svc = getattr(self.engine, "quote_service", None)
        if quote_svc is not None:
            cached = quote_svc.get_market_quotes_cache()
        else:
            from vnpy_ashare.ai.context_store import get_market_quotes_cache

            cached = get_market_quotes_cache()
        if cached:
            return cached, None

        try:
            from vnpy_ashare.screener.quotes_loader import load_market_quote_rows

            snapshot = load_market_quote_rows()
            return snapshot.rows, None
        except Exception as ex:
            return None, str(ex)

    def quote_rows_unavailable_message(self, reason: str | None = None) -> str:
        detail = reason or "未知原因"
        return f"暂无可用的市场行情数据（{detail}）。请运行「工具 → 立即执行 → 行情采集」，或打开「市场」页加载行情后再选股。"

    def screen_by_condition(
        self,
        name: str,
        quotes: list[dict[str, Any]],
        *,
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        from vnpy_ashare.screener.rules import apply_quote_preset

        return apply_quote_preset(name, quotes, top_n=top_n)

    def screen_quote_preset(self, name: str, *, top_n: int = 20) -> list[dict[str, Any]]:
        """基于缓存或 Redis 行情执行 quote 类预设。"""
        rows, err = self.load_quote_rows()
        if not rows:
            raise RuntimeError(self.quote_rows_unavailable_message(err))
        return self.screen_by_condition(name, rows, top_n=top_n)

    def run_request(self, request: ScreenerRequest) -> ScreenerRunResult:
        return run_screener(request)

    def run_pattern_screen(self, pattern: str, *, top_n: int = 20) -> ScreenerRunResult:
        from vnpy_ashare.screener.pattern_screen import (
            PatternScreenInput,
            resolve_pattern_screen,
            run_pattern_screen,
        )

        pattern_id, error = resolve_pattern_screen(PatternScreenInput(pattern=pattern, top_n=top_n))
        if error:
            raise ValueError(error)

        quote_rows = None
        if pattern_id == "theme_hot":
            quote_rows, err = self.load_quote_rows()
            if not quote_rows:
                raise RuntimeError(self.quote_rows_unavailable_message(err))

        def _load_bars(symbol: str, exchange) -> list:
            return self.engine.bar_service.load_bars(symbol, exchange, "daily")

        return run_pattern_screen(
            pattern_id,
            top_n=top_n,
            load_bars=_load_bars,
            quote_rows=quote_rows,
        )

    def set_screening_results(
        self,
        *,
        condition: str,
        rows: list[dict[str, Any]],
        updated_at: str | None = None,
    ) -> None:
        _set_screening_results(condition=condition, rows=rows, updated_at=updated_at)

    def get_screening_results(self) -> ScreeningResultContext | None:
        return _get_screening_results()

    def persist_run_result(
        self,
        result: ScreenerRunResult,
        *,
        nl_source: str = "",
        draft_id: str = "",
        trigger: str = "",
        extra_config: dict[str, Any] | None = None,
    ) -> None:
        """自动/确认选股执行后统一落库（context_store + run_store）。"""
        from vnpy_ashare.screener.run_store import save_run

        rows = list(result.rows)
        self.set_screening_results(
            condition=result.condition,
            rows=rows,
            updated_at=result.updated_at,
        )
        config: dict[str, Any] = dict(extra_config or {})
        if nl_source:
            config["nl_source"] = nl_source
        if draft_id:
            config["draft_id"] = draft_id
        if trigger:
            config["trigger"] = trigger
        save_run(
            condition=result.condition,
            source=result.source,
            rows=rows,
            total_scanned=result.total_scanned,
            config=config or None,
        )
        self.publish_page_context()

    def publish_page_context(self) -> None:
        """选股页激活或结果变更后，刷新 AI 侧栏上下文。"""
        publish_screener_page_context()

    # ── UI Facade（委托 screener 子模块，避免页面直连 store） ──

    def format_source_tag(self, source: str) -> str:
        from vnpy_ashare.screener.data_source import resolve_result_source_tag

        return resolve_result_source_tag(source)

    def resolve_export_columns(self, rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
        from vnpy_ashare.screener.export import resolve_export_columns

        return resolve_export_columns(rows)

    def export_csv(self, rows: list[dict[str, Any]], path: str) -> None:
        from vnpy_ashare.screener.export import export_rows_to_csv

        export_rows_to_csv(rows, path)

    def get_run_record(self, run_id: str):
        from vnpy_ashare.screener.run_store import get_run

        return get_run(run_id)

    def mark_run_read(self, run_id: str) -> None:
        from vnpy_ashare.screener.run_store import mark_run_read

        mark_run_read(run_id)

    def save_manual_run(
        self,
        result: ScreenerRunResult,
        request: ScreenerRequest | None,
    ) -> None:
        """策略选股页手动运行后落库。"""
        from vnpy_ashare.screener.runner import build_scheme_config

        config = build_scheme_config(request) if request else {}
        config["trigger"] = "manual"
        self.persist_run_result(result, extra_config=config)

    def list_schemes(self):
        from vnpy_ashare.screener.scheme_store import list_schemes

        return list_schemes()

    def save_scheme(self, name: str, config: dict[str, Any]):
        from vnpy_ashare.screener.scheme_store import save_scheme

        return save_scheme(name, config)

    def delete_scheme(self, scheme_id: str) -> None:
        from vnpy_ashare.screener.scheme_store import delete_scheme

        delete_scheme(scheme_id)

    def get_preset(self, name: str):
        from vnpy_ashare.screener.presets import get_preset

        return get_preset(name)

    @staticmethod
    def is_custom_preset(name: str) -> bool:
        from vnpy_ashare.screener.presets import SCREENER_CUSTOM

        return name == SCREENER_CUSTOM

    def build_scheme_config(self, request: ScreenerRequest) -> dict[str, Any]:
        from vnpy_ashare.screener.runner import build_scheme_config

        return build_scheme_config(request)

    # ── 运行历史（侧栏 / 收件箱） ──

    def list_run_history(self, limit: int = 40):
        from vnpy_ashare.screener.run_store import list_runs

        return list_runs(limit=limit)

    def delete_run_record(self, run_id: str) -> None:
        from vnpy_ashare.screener.run_store import delete_run

        delete_run(run_id)

    @staticmethod
    def is_auto_run_config(config: dict[str, Any] | None) -> bool:
        from vnpy_ashare.screener.run_store import is_auto_run

        return is_auto_run(config)

    @staticmethod
    def is_strategy_run_config(config: dict[str, Any] | None) -> bool:
        from vnpy_ashare.screener.run_store import is_strategy_run

        return is_strategy_run(config)

    @staticmethod
    def is_run_unread_config(config: dict[str, Any] | None) -> bool:
        from vnpy_ashare.screener.run_store import is_run_unread

        return is_run_unread(config)

    def find_latest_auto_run_for_job(self, job_id: str):
        """定时任务完成后定位最新自动选股记录。"""
        from vnpy_ashare.screener.run_store import is_auto_run, list_runs

        expected = f"scheduled_{job_id.removeprefix('screen_')}"
        for record in list_runs(limit=10):
            if not is_auto_run(record.config):
                continue
            if str(record.config.get("trigger", "")) == expected:
                return record
        runs = [r for r in list_runs(limit=5) if is_auto_run(r.config)]
        return runs[0] if runs else None

    def persist_scheduled_recipe_run(
        self,
        result: ScreenerRunResult,
        *,
        trigger: str,
        recipe_id: str,
    ) -> None:
        """定时/配方自动选股落库。"""
        from vnpy_ashare.screener.recipe import resolve_recipe
        from vnpy_ashare.screener.recipe_runner import build_reason_summary

        recipe = resolve_recipe(recipe_id)
        reason = (
            build_reason_summary(
                recipe=recipe,
                trigger=trigger,
                row_count=len(result.rows),
            )
            if recipe is not None
            else trigger
        )
        self.persist_run_result(
            result,
            trigger=trigger,
            extra_config={"recipe_id": recipe_id, "reason_summary": reason},
        )


def persist_scheduled_recipe_run(
    result: ScreenerRunResult,
    *,
    trigger: str,
    recipe_id: str,
) -> None:
    """无 Engine 时定时选股落库（委托 run_store + context_store）。"""
    from vnpy_ashare.screener.recipe import resolve_recipe
    from vnpy_ashare.screener.recipe_runner import build_reason_summary
    from vnpy_ashare.screener.run_store import save_run

    recipe = resolve_recipe(recipe_id)
    rows = list(result.rows)
    config: dict[str, Any] = {
        "trigger": trigger,
        "recipe_id": recipe_id,
        "reason_summary": build_reason_summary(
            recipe=recipe,
            trigger=trigger,
            row_count=len(rows),
        )
        if recipe is not None
        else trigger,
    }
    _set_screening_results(
        condition=result.condition,
        rows=rows,
        updated_at=result.updated_at,
    )
    save_run(
        condition=result.condition,
        source=result.source,
        rows=rows,
        total_scanned=result.total_scanned,
        config=config,
    )
    publish_screener_page_context()


def publish_screener_page_context() -> None:
    """推送选股页 AI 上下文（含悬浮球 actions）。"""
    from vnpy_llm.ui.floating_actions import enrich_context_with_actions

    ctx = _get_screening_results()
    if ctx is None or ctx.count == 0:
        extra = "当前无选股结果。请用户先在选股页运行方案，或询问如何设置筛选条件。"
        data = AiContextData(page="选股", extra=extra)
    else:
        preview = ctx.rows[:5]
        lines = [
            "你正在协助用户解读选股结果；数值来自规则引擎，禁止编造。",
            f"最近选股：「{ctx.condition}」命中 {ctx.count} 条",
        ]
        if ctx.updated_at:
            lines.append(f"更新时间：{ctx.updated_at}")
        lines.append("Top 预览：")
        for index, row in enumerate(preview, start=1):
            symbol = row.get("vt_symbol") or row.get("symbol", "")
            name = row.get("name", "")
            change = row.get("change_pct", "")
            lines.append(f"  {index}. {symbol} {name} {change}")
        if ctx.count > len(preview):
            lines.append(f"  … 另有 {ctx.count - len(preview)} 条，可调用 get_screening_context 查看")
        data = AiContextData(page="选股", extra="\n".join(lines))

    set_ai_context(enrich_context_with_actions(data))


def run_screening(
    quotes: list[dict[str, Any]] | None = None,
    *,
    preset: str,
    top_n: int = 20,
    min_change_pct: float | None = None,
    max_change_pct: float | None = None,
    min_turnover: float | None = None,
    scheme_id: str | None = None,
) -> ScreenerRunResult:
    """兼容旧入口；quotes 参数已弃用，统一走 runner。"""
    _ = quotes
    return run_screener(
        ScreenerRequest(
            preset=preset,
            top_n=top_n,
            min_change_pct=min_change_pct,
            max_change_pct=max_change_pct,
            min_turnover=min_turnover,
            scheme_id=scheme_id,
        )
    )
