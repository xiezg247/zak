"""本地数据弹窗。"""

from __future__ import annotations

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtGui, QtWidgets

from vnpy_ashare.ui.shell.page_shell import LocalPageWidget
from vnpy_common.ui.dialog_shell import setup_responsive_dialog


class LocalDataDialog(QtWidgets.QDialog):
    def __init__(
        self,
        main_engine: MainEngine,
        event_engine: EventEngine,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("LocalDataDialog")
        self.setWindowTitle("本地数据")
        setup_responsive_dialog(self, parent, min_width=1080, min_height=760)
        self.setSizeGripEnabled(True)

        self._page = LocalPageWidget(main_engine, event_engine)
        self._page.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        close_button = QtWidgets.QPushButton("关闭")
        close_button.setObjectName("SecondaryButton")
        close_button.setMinimumWidth(88)
        close_button.clicked.connect(self.reject)

        footer = QtWidgets.QWidget()
        footer.setObjectName("LocalDataDialogFooter")
        footer_row = QtWidgets.QHBoxLayout(footer)
        footer_row.setContentsMargins(16, 8, 16, 12)
        footer_row.addStretch(1)
        footer_row.addWidget(close_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._page, stretch=1)
        layout.addWidget(footer)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._page.activate()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._page.deactivate()
        super().closeEvent(event)


def show_local_data_dialog(
    main_engine: MainEngine,
    event_engine: EventEngine,
    parent: QtWidgets.QWidget | None = None,
) -> None:
    dialog = LocalDataDialog(main_engine, event_engine, parent=parent)
    dialog.exec()
