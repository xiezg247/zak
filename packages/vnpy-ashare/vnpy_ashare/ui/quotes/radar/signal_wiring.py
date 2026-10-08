"""雷达 board / resonance panel 信号 → controller 槽位绑定表。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

# (signal_attr, handler_attr on controller)
SignalWiring = tuple[str, str]

BOARD_WIRING: tuple[SignalWiring, ...] = (
    ("variant_changed", "_on_variant_changed"),
    ("row_activated", "_on_row_activated"),
    ("add_watchlist_requested", "_on_add_watchlist"),
    ("batch_add_watchlist_requested", "_on_batch_add_watchlist"),
    ("stock_analysis_requested", "_on_stock_analysis"),
    ("view_run_requested", "_on_view_run"),
    ("sector_flow_requested", "_on_sector_flow"),
    ("sector_rotation_requested", "_on_sector_rotation"),
    ("refresh_requested", "_on_card_refresh_requested"),
    ("quote_refresh_requested", "_on_card_quote_refresh_requested"),
    ("ai_requested", "request_card_ai"),
    ("auto_refresh_changed", "_on_auto_refresh_changed"),
    ("full_refresh_interval_changed", "_on_full_refresh_interval_changed"),
    ("mode_changed", "_on_board_mode_changed"),
    ("group_changed", "_on_board_group_changed"),
    ("outlook_strategy_changed", "_on_outlook_strategy_changed"),
)

PANEL_WIRING: tuple[SignalWiring, ...] = (
    ("row_activated", "_on_row_activated"),
    ("add_watchlist_requested", "_on_add_watchlist"),
    ("batch_add_watchlist_requested", "_on_resonance_batch_add_watchlist"),
    ("add_dragon_watchlist_requested", "_on_resonance_dragon_watchlist"),
    ("stock_analysis_requested", "_on_stock_analysis"),
    ("ai_resonance_requested", "request_resonance_ai_summary"),
    ("propose_trading_plan_requested", "_on_propose_trading_plan"),
    ("eod_leader_ai_requested", "request_eod_leader_ai"),
    ("open_screener_requested", "_on_open_screener_resonance"),
    ("open_leader_screener_requested", "_on_open_screener_leader"),
    ("resonance_weights_requested", "_on_resonance_weights_requested"),
    ("add_short_term_focus_requested", "_on_resonance_short_term_focus"),
)


def bind_signals(source: Any, owner: Any, wiring: Sequence[SignalWiring]) -> None:
    """将 source 上的 Signal 连接到 owner 的同名槽方法。"""
    for signal_name, handler_name in wiring:
        signal = getattr(source, signal_name)
        handler = getattr(owner, handler_name)
        signal.connect(handler)
