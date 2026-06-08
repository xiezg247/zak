"""数据管理页 AI 上下文。"""

from __future__ import annotations

from vnpy_ashare.ai.context import AiContextData
from vnpy_ashare.ai.session_context import set_ai_context
from vnpy_ashare.bar_store import iter_bar_overviews
from vnpy_llm.ui.floating_actions import enrich_context_with_actions


def build_data_manager_context() -> AiContextData:
    daily_symbols: set[tuple[str, str]] = set()
    minute_symbols: set[tuple[str, str]] = set()
    daily_bars = 0
    minute_bars = 0

    for overview in iter_bar_overviews(scope="daily"):
        daily_symbols.add((overview.symbol, overview.exchange.value))
        daily_bars += overview.count

    for overview in iter_bar_overviews(scope="1m"):
        minute_symbols.add((overview.symbol, overview.exchange.value))
        minute_bars += overview.count

    extra_lines = [
        "你正在协助用户查看本地 K 线数据覆盖；请基于工具与上下文回答，禁止编造。",
        f"日线：{len(daily_symbols)} 组标的，共 {daily_bars} 根 K 线",
        f"分钟线：{len(minute_symbols)} 组标的，共 {minute_bars} 根 K 线",
        "补全数据请引导用户使用「自选 / 本地」页或「工具 → 立即执行」。",
    ]
    return AiContextData(page="数据管理", extra="\n".join(extra_lines))


def sync_data_manager_context() -> None:
    set_ai_context(enrich_context_with_actions(build_data_manager_context()))
