"""行情数值展示格式化（无 UI 依赖，quotes 层与 Worker 共用）。"""

from __future__ import annotations

EMPTY_DISPLAY = "—"


def format_volume(volume: float) -> str:
    if volume <= 0:
        return EMPTY_DISPLAY
    if volume >= 1e8:
        return f"{volume / 1e8:.2f}亿"
    if volume >= 1e4:
        return f"{volume / 1e4:.2f}万"
    return f"{volume:.0f}"


def format_amount(amount: float) -> str:
    if amount <= 0:
        return EMPTY_DISPLAY
    if amount >= 1e8:
        return f"{amount / 1e8:.2f}亿"
    if amount >= 1e4:
        return f"{amount / 1e4:.2f}万"
    return f"{amount:.2f}"


def format_net_mf_amount(amount: float) -> str:
    if amount == 0:
        return EMPTY_DISPLAY
    return f"{amount:,.0f}万"


def format_pct(value: float | None) -> str:
    if value is None:
        return EMPTY_DISPLAY
    return f"{value:+.2f}%"
