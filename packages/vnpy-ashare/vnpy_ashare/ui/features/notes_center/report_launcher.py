"""从个股分析等页面打开笔记中心（与 dialog / open 解耦，避免 import 环）。"""

from __future__ import annotations

from collections.abc import Callable

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtWidgets


def open_notes_reports_center(
    main_engine: MainEngine,
    event_engine: EventEngine | None,
    *,
    focus_watchlist: Callable[[str, str], None] | None = None,
    initial_vt_symbol: str = "",
    parent: QtWidgets.QWidget | None = None,
) -> None:
    """打开笔记中心并定位到「分析报告」Tab。"""
    from vnpy_ashare.ui.features.notes_center.open import show_notes_center_dialog

    show_notes_center_dialog(
        main_engine,
        event_engine,
        focus_watchlist=focus_watchlist,
        initial_vt_symbol=initial_vt_symbol,
        initial_tab="reports",
        parent=parent,
    )
