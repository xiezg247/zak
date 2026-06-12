"""面板级通用 Widget：标签、卡片、指标块、Tab 页容器。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

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


def tile_grid(
    tiles: dict[str, MetricTile] | list[MetricTile],
    *,
    columns: int = 3,
    min_tile_width: int = 132,
) -> QtWidgets.QWidget:
    """指标卡片网格，避免单行过多导致挤压。"""
    items = list(tiles.values()) if isinstance(tiles, dict) else list(tiles)
    wrapper = QtWidgets.QWidget()
    grid = QtWidgets.QGridLayout(wrapper)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(10)
    for index, tile in enumerate(items):
        tile.setMinimumWidth(min_tile_width)
        tile.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        row, col = divmod(index, columns)
        grid.addWidget(tile, row, col)
    for col in range(columns):
        grid.setColumnStretch(col, 1)
    return wrapper


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


def configure_document_tab_widget(
    widget: QtWidgets.QTabWidget,
    *,
    object_name: str = "DocumentTabWidget",
) -> QtWidgets.QTabWidget:
    """Document 模式 Tab：去外框基线，避免 macOS 上出现白线。"""
    widget.setObjectName(object_name)
    widget.setDocumentMode(True)
    bar = widget.tabBar()
    bar.setDrawBase(False)
    bar.setExpanding(False)
    return widget


def document_tab_widget(*tabs: tuple[str, QtWidgets.QWidget]) -> QtWidgets.QTabWidget:
    widget = configure_document_tab_widget(QtWidgets.QTabWidget())
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


def initial_dialog_size(
    *,
    min_width: int = 1080,
    min_height: int = 760,
    width_ratio: float = 0.82,
    height_ratio: float = 0.86,
    max_width: int = 1440,
    max_height: int = 1000,
) -> tuple[int, int]:
    screen = QtWidgets.QApplication.primaryScreen()
    if screen is None:
        return max(min_width, 1180), max(min_height, 820)
    rect = screen.availableGeometry()
    width = min(max(int(rect.width() * width_ratio), min_width), max_width)
    height = min(max(int(rect.height() * height_ratio), min_height), max_height)
    return width, height
