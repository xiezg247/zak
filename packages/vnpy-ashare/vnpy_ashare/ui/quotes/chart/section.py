"""自选 / 本地页右侧 K 线侧栏（整栏折叠）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.quotes.chart.section_settings import (
    load_chart_section_expanded,
    save_chart_section_expanded,
)
from vnpy_common.ui.theme import theme_manager

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

CHART_SIDE_HANDLE_WIDTH = 24
CHART_SIDE_COLLAPSED_WIDTH = CHART_SIDE_HANDLE_WIDTH
CHART_SIDE_EXPANDED_MIN_WIDTH = 420
CHART_SIDE_EXPANDED_DEPTH_MIN_WIDTH = 560
COLLAPSE_BUTTON_SIZE = 20


def chart_side_collapse_arrow(expanded: bool) -> QtCore.Qt.ArrowType:
    """侧栏左缘按钮：展开时向左收起，折叠时向右展开。"""
    return QtCore.Qt.ArrowType.LeftArrow if expanded else QtCore.Qt.ArrowType.RightArrow


class ChartSectionPanel(QtWidgets.QWidget):
    """右侧 K 线侧栏：左缘居中折叠钮，折叠/展开整个控件（报价 + 图表 + 五档等）。"""

    expansion_changed = QtCore.Signal(bool)

    def __init__(self, page_name: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._page_name = page_name
        self._expanded = load_chart_section_expanded(page_name)
        self._content_widget: QtWidgets.QWidget | None = None

        self.setObjectName("ChartSectionPanel")
        theme_manager().bind_stylesheet(self)

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        handle = QtWidgets.QWidget(self)
        handle.setObjectName("ChartSectionHandle")
        handle.setFixedWidth(CHART_SIDE_HANDLE_WIDTH)
        handle_layout = QtWidgets.QVBoxLayout(handle)
        handle_layout.setContentsMargins(0, 0, 0, 0)
        handle_layout.setSpacing(0)

        self._collapse_button = QtWidgets.QToolButton(handle)
        self._collapse_button.setObjectName("ChartSectionCollapseButton")
        self._collapse_button.setCheckable(True)
        self._collapse_button.setAutoRaise(True)
        self._collapse_button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._collapse_button.setFixedSize(COLLAPSE_BUTTON_SIZE, COLLAPSE_BUTTON_SIZE)
        self._collapse_button.clicked.connect(self._on_collapse_toggled)

        handle_layout.addStretch(1)
        handle_layout.addWidget(
            self._collapse_button,
            alignment=QtCore.Qt.AlignmentFlag.AlignHCenter,
        )
        handle_layout.addStretch(1)

        self._content = QtWidgets.QWidget(self)
        self._content.setObjectName("ChartSectionContent")
        self._content_layout = QtWidgets.QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(4)

        root.addWidget(handle)
        root.addWidget(self._content, stretch=1)

        self._apply_expanded(self._expanded, emit=False)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_content(self, widget: QtWidgets.QWidget) -> None:
        if self._content_widget is not None:
            self._content_layout.removeWidget(self._content_widget)
            self._content_widget.setParent(None)
        self._content_widget = widget
        self._content_layout.addWidget(widget, stretch=1)
        self._apply_expanded(self._expanded, emit=False)

    def set_chart_body(self, widget: QtWidgets.QWidget) -> None:
        """兼容旧调用：整栏内容而非仅 K 线图。"""
        self.set_content(widget)

    def set_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded
        save_chart_section_expanded(self._page_name, expanded)
        self._apply_expanded(expanded, emit=emit)

    def _on_collapse_toggled(self, expanded: bool) -> None:
        self.set_expanded(expanded)

    def _sync_collapse_button(self) -> None:
        self._collapse_button.blockSignals(True)
        self._collapse_button.setChecked(self._expanded)
        self._collapse_button.setArrowType(chart_side_collapse_arrow(self._expanded))
        self._collapse_button.blockSignals(False)

    def _apply_expanded(self, expanded: bool, *, emit: bool) -> None:
        self._sync_collapse_button()
        self._content.setVisible(expanded)
        if expanded:
            self.setMinimumWidth(CHART_SIDE_EXPANDED_MIN_WIDTH)
            self.setMaximumWidth(16777215)
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Preferred,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
        else:
            self.setMinimumWidth(CHART_SIDE_COLLAPSED_WIDTH)
            self.setMaximumWidth(CHART_SIDE_COLLAPSED_WIDTH)
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Fixed,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
        self.updateGeometry()
        if emit:
            self.expansion_changed.emit(expanded)


def chart_side_expanded_min_width(page: QuotesPage) -> int:
    depth = bool(page.config.show_depth_panel)
    return CHART_SIDE_EXPANDED_DEPTH_MIN_WIDTH if depth else CHART_SIDE_EXPANDED_MIN_WIDTH


def sync_chart_splitter_for_expansion(page: QuotesPage, expanded: bool) -> None:
    """折叠时收窄 splitter 右侧整栏，仅保留左缘折叠钮。"""
    section = getattr(page, "chart_section", None)
    splitter = getattr(page, "_splitter", None)
    if section is None or splitter is None or splitter.count() < 2:
        return

    expanded_min = chart_side_expanded_min_width(page)

    if expanded:
        section.setMinimumWidth(expanded_min)
        section.setMaximumWidth(16777215)
        saved = getattr(page, "_chart_splitter_saved_state", None)
        if isinstance(saved, QtCore.QByteArray) and not saved.isEmpty():
            splitter.restoreState(saved)
        return

    state = splitter.saveState()
    if isinstance(state, QtCore.QByteArray) and not state.isEmpty():
        page._chart_splitter_saved_state = state

    section.setMinimumWidth(CHART_SIDE_COLLAPSED_WIDTH)
    section.setMaximumWidth(CHART_SIDE_COLLAPSED_WIDTH)
    sizes = splitter.sizes()
    total = max(sum(sizes), splitter.width(), expanded_min + 200)
    splitter.blockSignals(True)
    splitter.setSizes([total - CHART_SIDE_COLLAPSED_WIDTH, CHART_SIDE_COLLAPSED_WIDTH])
    splitter.blockSignals(False)
