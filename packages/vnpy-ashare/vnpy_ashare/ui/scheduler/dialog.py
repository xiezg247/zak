"""定时任务弹窗。"""

from __future__ import annotations

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ui.scheduler.scheduler_jobs_widget import _prevent_dialog_default_button
from vnpy_ashare.ui.scheduler.scheduler_page import SchedulerPageWidget
from vnpy_common.ui.dialog_shell import setup_responsive_dialog
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.theme.build_extra import build_scheduler_page_stylesheet
from vnpy_common.ui.theme.manager import theme_manager

_OPEN_DIALOG: SchedulerDialog | None = None


def _clear_open_dialog(*_args: object) -> None:
    global _OPEN_DIALOG
    _OPEN_DIALOG = None


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

        close_button = QtWidgets.QPushButton("关闭")
        close_button.setObjectName("SecondaryButton")
        close_button.setMinimumWidth(88)
        _prevent_dialog_default_button(close_button)
        close_button.clicked.connect(self.close)

        footer = QtWidgets.QWidget()
        footer.setObjectName("SchedulerDialogFooter")
        footer_row = QtWidgets.QHBoxLayout(footer)
        footer_row.setContentsMargins(16, 8, 16, 12)
        footer_row.addStretch(1)
        footer_row.addWidget(close_button)
        layout.addWidget(footer)

        theme_manager().bind_stylesheet(self, extra=build_scheduler_page_stylesheet)

    def accept(self) -> None:
        """非模态工具窗：子按钮勿触发 QDialog.accept 导致窗口被关闭。"""

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._page.activate()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        running_names = self._page.deactivate()
        event.accept()
        super().closeEvent(event)
        if running_names:
            names = "、".join(running_names)
            page_notify(
                self.parentWidget(),
                f"{names} 仍在后台执行，可再次打开「定时任务」查看进度。",
            )


def show_scheduler_dialog(
    main_engine: MainEngine,
    event_engine: EventEngine,
    parent: QtWidgets.QWidget | None = None,
) -> None:
    global _OPEN_DIALOG
    if _OPEN_DIALOG is not None:
        try:
            _OPEN_DIALOG.raise_()
            _OPEN_DIALOG.activateWindow()
            return
        except RuntimeError:
            _OPEN_DIALOG = None

    dialog = SchedulerDialog(main_engine, event_engine, parent=parent)
    dialog.setWindowModality(QtCore.Qt.WindowModality.NonModal)
    dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    _OPEN_DIALOG = dialog
    dialog.destroyed.connect(_clear_open_dialog)
    dialog.show()
