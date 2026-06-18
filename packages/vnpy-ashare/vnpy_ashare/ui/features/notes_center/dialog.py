"""笔记中心对话框。"""

from __future__ import annotations

from collections.abc import Callable

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtGui, QtWidgets

from vnpy_ashare.ui.features.notes_center.widget import NotesCenterWidget
from vnpy_common.ui.dialog_shell import setup_responsive_dialog
from vnpy_common.ui.theme.manager import theme_manager


class NotesCenterDialog(QtWidgets.QDialog):
    def __init__(
        self,
        main_engine: MainEngine,
        event_engine: EventEngine | None,
        *,
        focus_watchlist: Callable[[str, str], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("NotesCenterDialog")
        self.setWindowTitle("笔记中心")
        setup_responsive_dialog(
            self,
            parent,
            min_width=1080,
            min_height=680,
            width_ratio=0.88,
            height_ratio=0.86,
            max_width=1520,
            max_height=960,
        )

        self._page = NotesCenterWidget(
            main_engine,
            event_engine,
            focus_watchlist=focus_watchlist,
            parent=self,
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._page)

        theme_manager().bind_stylesheet(self)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._page.activate()

    def select_vt_symbol(self, vt_symbol: str) -> None:
        self._page.select_vt_symbol(vt_symbol)

    def focus_tab(self, tab: str) -> None:
        self._page.focus_tab(tab)
