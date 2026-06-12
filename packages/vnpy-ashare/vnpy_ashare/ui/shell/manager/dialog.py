"""数据管理弹窗。"""

from __future__ import annotations

from collections.abc import Callable

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtGui, QtWidgets

from vnpy_ashare.ui.shell.manager.widget import ManagerWidget
from vnpy_common.ui.dialog_shell import setup_responsive_dialog


class DataManagerDialog(QtWidgets.QDialog):
    def __init__(
        self,
        main_engine: MainEngine,
        event_engine: EventEngine,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DataManagerDialog")
        self.setWindowTitle("数据管理")
        setup_responsive_dialog(self, parent, min_width=880, min_height=560)

        self._page = ManagerWidget(main_engine, event_engine)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._page)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        if hasattr(self._page, "activate"):
            self._page.activate()


def show_data_manager_dialog(
    main_engine: MainEngine,
    event_engine: EventEngine,
    *,
    ensure_apps: Callable[[], None] | None = None,
    parent: QtWidgets.QWidget | None = None,
) -> None:
    if ensure_apps is not None:
        ensure_apps()
    dialog = DataManagerDialog(main_engine, event_engine, parent=parent)
    dialog.exec()
