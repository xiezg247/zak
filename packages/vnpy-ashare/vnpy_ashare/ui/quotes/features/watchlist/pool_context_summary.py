"""自选页四层池摘要文案（无 UI 依赖，供 context_bar / 单测）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences.watchlist_signal import SIGNAL_PANEL_MAX_SYMBOLS
from vnpy_ashare.services.watchlist import WATCHLIST_MAX_ITEMS
from vnpy_ashare.storage.repositories.positions import POSITION_MAX_ITEMS

SHORT_TERM_OBSERVATION_MAX = 5


def format_pool_context_summary(
    *,
    pool_count: int,
    observation_count: int,
    signal_count: int,
    position_count: int,
) -> str:
    return (
        f"自选 {pool_count}/{WATCHLIST_MAX_ITEMS}"
        f" · 观察组 {observation_count}/{SHORT_TERM_OBSERVATION_MAX}"
        f" · 信号 {signal_count}/{SIGNAL_PANEL_MAX_SYMBOLS}"
        f" · 持仓 {position_count}/{POSITION_MAX_ITEMS}"
    )
