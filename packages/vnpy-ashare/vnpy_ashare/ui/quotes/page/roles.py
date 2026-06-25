"""行情页角色常量（自选池 / 策略监控等）。"""

from __future__ import annotations

WATCHLIST_PAGE = "自选"
STRATEGY_MONITOR_PAGE = "策略监控"
STRATEGY_MONITOR_NAV_KEY = "strategy_monitor"

WATCHLIST_POOL_PAGES: frozenset[str] = frozenset({WATCHLIST_PAGE, STRATEGY_MONITOR_PAGE})


def uses_watchlist_pool(page_name: str) -> bool:
    return page_name in WATCHLIST_POOL_PAGES


def is_strategy_monitor_page(page_name: str) -> bool:
    return page_name == STRATEGY_MONITOR_PAGE
