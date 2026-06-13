"""定时任务弹窗。"""

from __future__ import annotations

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtGui, QtWidgets

from vnpy_ashare.ui.scheduler.scheduler_page import SchedulerPageWidget
from vnpy_common.ui.dialog_shell import setup_responsive_dialog
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.build_extra import build_scheduler_page_stylesheet


class SchedulerDialog(QtWidgets.QDialog):
    def __init__(
        self,
        main_engine: MainEngine,
        event_engine: EventEngine,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SchedulerDialog")
        self.setWindowTitle("定时任务")
        setup_responsive_dialog(self, parent, min_width=920, min_height=640)
        self.setSizeGripEnabled(True)

        self._page = SchedulerPageWidget(main_engine, event_engine)
        self._page.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._page, stretch=1)

        theme_manager().bind_stylesheet(self, extra=build_scheduler_page_stylesheet)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._page.activate()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._page.deactivate()
        super().closeEvent(event)


def show_scheduler_dialog(
    main_engine: MainEngine,
    event_engine: EventEngine,
    parent: QtWidgets.QWidget | None = None,
) -> None:
    dialog = SchedulerDialog(main_engine, event_engine, parent=parent)
    dialog.exec()
