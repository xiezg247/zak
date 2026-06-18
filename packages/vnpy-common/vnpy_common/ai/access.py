"""AI 上下文访问桥：vnpy_ashare 注册实现，vnpy_llm 只读。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from vnpy_common.ai.protocol import AiContextData

_get_ai_context: Callable[[], AiContextData] | None = None
_register_listener: Callable[[Callable[[AiContextData], None]], None] | None = None
_get_screening_results: Callable[[], Any] | None = None
_stock_completion_builder: Callable[..., list[Any]] | None = None


def register_context_store(
    *,
    get_ai_context: Callable[[], AiContextData],
    register_context_listener: Callable[[Callable[[AiContextData], None]], None],
) -> None:
    global _get_ai_context, _register_listener
    _get_ai_context = get_ai_context
    _register_listener = register_context_listener


def register_screening_accessor(get_screening_results: Callable[[], Any]) -> None:
    global _get_screening_results
    _get_screening_results = get_screening_results


def register_stock_completion_builder(builder: Callable[..., list[Any]]) -> None:
    global _stock_completion_builder
    _stock_completion_builder = builder


def get_ai_context() -> AiContextData:
    if _get_ai_context is None:
        return AiContextData()
    return _get_ai_context()


def register_context_listener(callback: Callable[[AiContextData], None]) -> None:
    if _register_listener is None:
        return
    _register_listener(callback)


def get_screening_results() -> Any:
    if _get_screening_results is None:
        return None
    return _get_screening_results()


_panel_actions_builder: Callable[..., list[Any]] | None = None


def register_panel_actions_builder(builder: Callable[..., list[Any]]) -> None:
    global _panel_actions_builder
    _panel_actions_builder = builder


def build_quick_actions_for_panel(data: AiContextData, *, mode: str) -> list[Any]:
    if _panel_actions_builder is None:
        return list(data.actions)
    return _panel_actions_builder(data, mode=mode)


def build_stock_completion_items(*args: Any, **kwargs: Any) -> list[Any]:
    if _stock_completion_builder is None:
        return []
    return _stock_completion_builder(*args, **kwargs)


_market_prompt_builder: Callable[..., str] | None = None
_persist_team_report: Callable[..., dict[str, Any] | None] | None = None
_team_report_href: Callable[[int, str], str] | None = None


def register_market_prompt_builder(builder: Callable[..., str]) -> None:
    global _market_prompt_builder
    _market_prompt_builder = builder


def build_market_ai_prompt(*, focus: str = "intraday") -> str:
    if _market_prompt_builder is None:
        return ""
    return _market_prompt_builder(focus=focus)


def register_team_report_bridge(
    *,
    persist_team_analysis_report: Callable[..., dict[str, Any] | None],
    team_report_href: Callable[[int, str], str],
) -> None:
    global _persist_team_report, _team_report_href
    _persist_team_report = persist_team_analysis_report
    _team_report_href = team_report_href


def persist_team_analysis_report(
    symbol: str,
    body: str,
    *,
    name: str = "",
    team_scores: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if _persist_team_report is None:
        return None
    return _persist_team_report(symbol, body, name=name, team_scores=team_scores)


def team_report_href(report_id: int, vt_symbol: str) -> str:
    if _team_report_href is None:
        return ""
    return _team_report_href(report_id, vt_symbol)
