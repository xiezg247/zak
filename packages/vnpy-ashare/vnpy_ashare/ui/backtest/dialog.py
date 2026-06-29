"""策略回测与回测对比弹窗。"""

from __future__ import annotations

from collections.abc import Callable

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_common.ui.dialog_shell import setup_responsive_dialog

_OPEN_BACKTEST_DIALOG: BacktestToolDialog | None = None
_OPEN_BATCH_BACKTEST_DIALOG: BacktestToolDialog | None = None


def _prevent_dialog_default_button(button: QtWidgets.QPushButton) -> None:
    """QDialog 内普通按钮默认 autoDefault，点击可能误 accept 关闭父弹窗。"""
    button.setAutoDefault(False)
    button.setDefault(False)


def _build_dialog_footer(dialog: QtWidgets.QDialog) -> QtWidgets.QWidget:
    close_button = QtWidgets.QPushButton("关闭")
    close_button.setObjectName("SecondaryButton")
    close_button.setMinimumWidth(88)
    _prevent_dialog_default_button(close_button)
    close_button.clicked.connect(dialog.close)

    footer = QtWidgets.QWidget()
    footer.setObjectName("BacktestDialogFooter")
    footer_row = QtWidgets.QHBoxLayout(footer)
    footer_row.setContentsMargins(16, 8, 16, 12)
    footer_row.addStretch(1)
    footer_row.addWidget(close_button)
    return footer


class BacktestToolDialog(QtWidgets.QDialog):
    """非模态工具窗：关闭时隐藏，保留页面状态。"""

    def __init__(
        self,
        *,
        title: str,
        object_name: str,
        page: QtWidgets.QWidget,
        parent: QtWidgets.QWidget | None = None,
        min_width: int,
        min_height: int,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setWindowTitle(title)
        setup_responsive_dialog(self, parent, min_width=min_width, min_height=min_height)
        self.setSizeGripEnabled(True)

        self._page = page
        page.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(page, stretch=1)
        layout.addWidget(_build_dialog_footer(self))

    def accept(self) -> None:
        """非模态工具窗：子按钮勿触发 QDialog.accept 导致窗口被关闭。"""

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        if hasattr(self._page, "activate"):
            self._page.activate()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if hasattr(self._page, "deactivate"):
            self._page.deactivate()
        event.ignore()
        self.hide()


def _present_dialog(
    dialog: BacktestToolDialog | None,
    *,
    create_dialog: Callable[[], BacktestToolDialog],
    on_present: Callable[[], None] | None = None,
) -> BacktestToolDialog:
    if dialog is None:
        dialog = create_dialog()
        dialog.setWindowModality(QtCore.Qt.WindowModality.NonModal)
    if on_present is not None:
        on_present()
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog


def show_backtest_dialog(
    page: QtWidgets.QWidget,
    *,
    parent: QtWidgets.QWidget | None = None,
    on_present: Callable[[], None] | None = None,
) -> None:
    global _OPEN_BACKTEST_DIALOG

    def _create_dialog() -> BacktestToolDialog:
        return BacktestToolDialog(
            title="策略回测",
            object_name="BacktestDialog",
            page=page,
            parent=parent,
            min_width=1100,
            min_height=720,
        )

    _OPEN_BACKTEST_DIALOG = _present_dialog(
        _OPEN_BACKTEST_DIALOG,
        create_dialog=_create_dialog,
        on_present=on_present,
    )


def show_batch_backtest_dialog(
    page: QtWidgets.QWidget,
    *,
    parent: QtWidgets.QWidget | None = None,
    on_present: Callable[[], None] | None = None,
) -> None:
    global _OPEN_BATCH_BACKTEST_DIALOG

    def _create_dialog() -> BacktestToolDialog:
        return BacktestToolDialog(
            title="回测对比",
            object_name="BatchBacktestDialog",
            page=page,
            parent=parent,
            min_width=960,
            min_height=640,
        )

    _OPEN_BATCH_BACKTEST_DIALOG = _present_dialog(
        _OPEN_BATCH_BACKTEST_DIALOG,
        create_dialog=_create_dialog,
        on_present=on_present,
    )
