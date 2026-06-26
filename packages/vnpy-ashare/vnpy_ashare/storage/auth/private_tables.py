"""按 user_id 隔离的 app schema 表（prune / 多用户清理用）。"""

from __future__ import annotations

PRIVATE_TABLES: tuple[str, ...] = (
    "watchlist",
    "watchlist_groups",
    "watchlist_group_members",
    "watchlist_positions",
    "stock_note_memos",
    "stock_note_entries",
    "stock_analysis_reports",
    "trading_plans",
    "trading_plan_symbols",
    "trading_playbook_discipline_daily",
    "screener_schemes",
    "screener_recipes",
    "screener_runs",
    "backtest_runs",
    "feed_subscriptions",
    "feed_cursors",
    "notify_delivery_log",
)
