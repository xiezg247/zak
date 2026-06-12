"""内容区加载遮罩（表格 / 弹窗 Tab 复用）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets


class ContentLoadingOverlay(QtWidgets.QWidget):
    """半透明遮罩 + 居中 indeterminate 进度条。"""

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("ContentLoadingOverlay")
        self.hide()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch(1)

        center_row = QtWidgets.QHBoxLayout()
        center_row.addStretch(1)

        panel = QtWidgets.QWidget()
        panel.setObjectName("ContentLoadingPanel")
        panel_layout = QtWidgets.QVBoxLayout(panel)
        panel_layout.setContentsMargins(32, 24, 32, 24)
        panel_layout.setSpacing(10)

        self._progress = QtWidgets.QProgressBar()
        self._progress.setObjectName("ContentLoadingBar")
        self._progress.setRange(0, 0)
        self._progress.setFixedWidth(240)

        self._title = QtWidgets.QLabel("正在加载…")
        self._title.setObjectName("ContentLoadingTitle")
        self._title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self._hint = QtWidgets.QLabel("")
        self._hint.setObjectName("ContentLoadingHint")
        self._hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)
        self._hint.hide()

        panel_layout.addWidget(self._progress, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        panel_layout.addWidget(self._title)
        panel_layout.addWidget(self._hint)

        center_row.addWidget(panel)
        center_row.addStretch(1)
        layout.addLayout(center_row)
        layout.addStretch(1)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[name-defined]
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        super().resizeEvent(event)

    def show_loading(self, title: str, *, hint: str = "") -> None:
        self._title.setText(title)
        if hint:
            self._hint.setText(hint)
            self._hint.show()
        else:
            self._hint.hide()
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()

    def hide_loading(self) -> None:
        self.hide()


class LoadingContentHost(QtWidgets.QWidget):
    """内容容器：子 widget 填满，加载遮罩覆盖其上。"""

    def __init__(self, content: QtWidgets.QWidget, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(content, stretch=1)
        self._overlay = ContentLoadingOverlay(self)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[name-defined]
        super().resizeEvent(event)
        self._overlay.setGeometry(self.rect())

    def show_loading(self, title: str, *, hint: str = "") -> None:
        self._overlay.show_loading(title, hint=hint)

    def hide_loading(self) -> None:
        self._overlay.hide_loading()
