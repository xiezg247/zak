"""投研团队模式：股票代码解析与上下文回退。"""

from __future__ import annotations

from vnpy_common.ai.symbol_navigation import get_symbol_navigation


def normalize_symbol_code(raw: str) -> str | None:
    """将各类代码格式规范为 vt_symbol（如 600519.SSE）。"""
    nav = get_symbol_navigation()
    if nav is None:
        return None
    return nav.normalize_vt_symbol(raw)


def resolve_team_symbol(
    *,
    user_text: str,
    context_symbol: str = "",
    context_exchange: str = "",
) -> str | None:
    """从用户消息或终端选中标的解析团队分析目标代码。"""
    nav = get_symbol_navigation()
    if nav is None:
        return None
    return nav.resolve_team_symbol(
        user_text=user_text,
        context_symbol=context_symbol,
        context_exchange=context_exchange,
    )
