"""面板级通用 Widget：标签、卡片、指标块、Tab 页容器。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_common.ui.scroll_area import TERMINAL_SCROLL_AREA, frameless_scroll_area


def section_title(text: str) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setObjectName("SectionLabel")
    return label


def hint_label(text: str = "") -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setObjectName("PageHint")
    label.setWordWrap(True)
    return label


def panel_status_label(text: str = "") -> QtWidgets.QLabel:
    label = hint_label(text)
    label.setObjectName("PanelStatus")
    return label


def content_card(
    *widgets: QtWidgets.QWidget,
    margins: tuple[int, int, int, int] = (12, 10, 12, 10),
    spacing: int = 6,
) -> QtWidgets.QFrame:
    frame = QtWidgets.QFrame()
    frame.setObjectName("ContentCard")
    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    for widget in widgets:
        layout.addWidget(widget)
    return frame


def frameless_scroll(
    widget: QtWidgets.QWidget,
    *,
    area_name: str = TERMINAL_SCROLL_AREA,
) -> QtWidgets.QScrollArea:
    return frameless_scroll_area(widget, area_name=area_name)


class MetricTile(QtWidgets.QFrame):
    """指标卡片：标题 + 主值 + 可选副标题。"""

    def __init__(
        self,
        title: str,
        value: str = "—",
        *,
        subtitle: str = "",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MetricTile")
        self._title = QtWidgets.QLabel(title)
        self._title.setObjectName("MetricTileTitle")
        self._value = QtWidgets.QLabel(value)
        self._value.setObjectName("MetricTileValue")
        self._subtitle = QtWidgets.QLabel(subtitle)
        self._subtitle.setObjectName("MetricTileSub")
        self._subtitle.setVisible(bool(subtitle))

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        layout.addWidget(self._title)
        layout.addWidget(self._value)
        layout.addWidget(self._subtitle)

    def set_value(self, value: str, *, subtitle: str = "", color: str = "") -> None:
        self._value.setText(value)
        if subtitle:
            self._subtitle.setText(subtitle)
            self._subtitle.setVisible(True)
        else:
            self._subtitle.setVisible(False)
        if color:
            self._value.setStyleSheet(f"color: {color};")
        else:
            self._value.setStyleSheet("")


def tab_page(
    *widgets: QtWidgets.QWidget | int,
    margins: tuple[int, int, int, int] = (4, 8, 4, 4),
    stretch_index: int | None = None,
) -> QtWidgets.QWidget:
    page = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(page)
    layout.setContentsMargins(*margins)
    layout.setSpacing(10)
    for index, widget in enumerate(widgets):
        if isinstance(widget, int):
            layout.addStretch(widget)
        elif stretch_index == index:
            layout.addWidget(widget, stretch=1)
        else:
            layout.addWidget(widget)
    return page


def document_tab_widget(*tabs: tuple[str, QtWidgets.QWidget]) -> QtWidgets.QTabWidget:
    widget = QtWidgets.QTabWidget()
    widget.setObjectName("DocumentTabWidget")
    widget.setDocumentMode(True)
    for title, page in tabs:
        widget.addTab(page, title)
    return widget


def center_dialog_on_parent(dialog: QtWidgets.QDialog, parent: QtWidgets.QWidget | None) -> None:
    if parent is not None:
        center = parent.geometry().center()
        frame = dialog.frameGeometry()
        frame.moveCenter(center)
        dialog.move(frame.topLeft())
        return
    screen = QtWidgets.QApplication.primaryScreen()
    if screen is None:
        return
    center = screen.availableGeometry().center()
    frame = dialog.frameGeometry()
    frame.moveCenter(center)
    dialog.move(frame.topLeft())


def initial_dialog_size(*, min_width: int = 1080, min_height: int = 760) -> tuple[int, int]:
    screen = QtWidgets.QApplication.primaryScreen()
    if screen is None:
        return 1180, 820
    rect = screen.availableGeometry()
    width = min(max(int(rect.width() * 0.82), min_width), 1440)
    height = min(max(int(rect.height() * 0.86), min_height), 1000)
    return width, height
