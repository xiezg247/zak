"""选股 Service（委托 screener.runner）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context import AiContextData
from vnpy_ashare.ai.context_store import (
    ScreeningResultContext,
    get_screening_results as _get_screening_results,
    set_ai_context,
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
        return (
            f"暂无可用的市场行情数据（{detail}）。"
            "请运行「工具 → 立即执行 → 行情采集」，或打开「市场」页加载行情后再选股。"
        )

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

    def publish_page_context(self) -> None:
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
            lines.append(
                f"  … 另有 {ctx.count - len(preview)} 条，可调用 get_screening_context 查看"
            )
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
