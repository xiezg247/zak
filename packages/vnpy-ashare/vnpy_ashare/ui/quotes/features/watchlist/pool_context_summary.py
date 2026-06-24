"""自选页三层池摘要文案（无 UI 依赖，供 context_bar / 单测）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences.watchlist_signal import SIGNAL_PANEL_MAX_SYMBOLS
from vnpy_ashare.services.position import PositionService
from vnpy_ashare.services.watchlist import WATCHLIST_MAX_ITEMS


def format_pool_context_summary(
    *,
    pool_count: int,
    signal_count: int,
    position_count: int,
) -> str:
    return f"自选 {pool_count}/{WATCHLIST_MAX_ITEMS} · 信号 {signal_count}/{SIGNAL_PANEL_MAX_SYMBOLS} · 持仓 {position_count}/{PositionService.max_items}"
