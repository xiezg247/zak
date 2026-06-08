"""选股 Service（委托 screener.runner）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.screener.presets import (
    SCREENER_CHANGE_TOP,
    SCREENER_CUSTOM,
    SCREENER_LARGE_CAP,
    SCREENER_LOW_PE,
    SCREENER_MONEYFLOW_IN,
    SCREENER_TURNOVER,
    SCREENER_VOLUME_SURGE,
    list_builtin_preset_names,
    list_quote_preset_names,
    list_tushare_preset_names,
)
from vnpy_ashare.screener.runner import ScreenerRequest, ScreenerRunResult, run_screener
from vnpy_ashare.services.base import BaseService

AVAILABLE_SCREENERS = list_builtin_preset_names()


class ScreeningService(BaseService):
    """执行选股条件，返回候选标的。"""

    def list_screeners(self) -> list[str]:
        return list_builtin_preset_names()

    def list_quote_screeners(self) -> list[str]:
        return list_quote_preset_names()

    def list_tushare_screeners(self) -> list[str]:
        return list_tushare_preset_names()

    def screen_by_condition(
        self,
        name: str,
        quotes: list[dict[str, Any]],
        *,
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        from vnpy_ashare.screener.rules import apply_quote_preset

        return apply_quote_preset(name, quotes, top_n=top_n)

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
