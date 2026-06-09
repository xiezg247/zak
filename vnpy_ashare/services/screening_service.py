"""选股 Service（委托 screener.runner）。"""

from __future__ import annotations

from typing import Any

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
        """加载行情行：优先 session 缓存，其次 Redis 全市场快照。"""
        from vnpy_ashare.ai.session_context import get_market_quotes_cache

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
