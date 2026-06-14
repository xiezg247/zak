"""笔记中心入口。"""

from __future__ import annotations

from collections.abc import Callable

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.features.notes_center.dialog import NotesCenterDialog


def show_notes_center_dialog(
    main_engine: MainEngine,
    event_engine: EventEngine | None,
    *,
    focus_watchlist: Callable[[str, str], None] | None = None,
    initial_vt_symbol: str = "",
    initial_tab: str = "memo",
    parent: QtWidgets.QWidget | None = None,
) -> None:
    dialog = NotesCenterDialog(
        main_engine,
        event_engine,
        focus_watchlist=focus_watchlist,
        parent=parent,
    )
    if initial_vt_symbol.strip():
        dialog.select_vt_symbol(initial_vt_symbol.strip())
    if initial_tab.strip():
        dialog.focus_tab(initial_tab.strip())
    dialog.exec()

