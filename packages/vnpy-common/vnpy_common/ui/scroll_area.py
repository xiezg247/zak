"""滚动区 / 表格滚动条统一封装（objectName + 策略）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

# 与 build_scrollbar.build_terminal_scrollbar_stylesheet 中的命名一致
TERMINAL_SCROLL_AREA = "TerminalScrollArea"
TERMINAL_SCROLL_BAR_VERTICAL = "TerminalScrollBarVertical"
TERMINAL_SCROLL_BAR_HORIZONTAL = "TerminalScrollBarHorizontal"
MARKET_TABLE_SCROLL_BAR = "MarketTableScroll"
AI_MESSAGE_SCROLL_AREA = "AiMessageScroll"
AI_MESSAGE_SCROLL_BAR = "AiMessageScrollBar"


def style_scroll_bar(
    bar: QtWidgets.QScrollBar,
    *,
    orientation: QtCore.Qt.Orientation,
    name: str,
) -> None:
    del orientation
    bar.setObjectName(name)
    bar.setStyleSheet("")


def style_scroll_area(
    scroll: QtWidgets.QScrollArea,
    *,
    area_name: str = TERMINAL_SCROLL_AREA,
    bar_vertical_name: str = TERMINAL_SCROLL_BAR_VERTICAL,
    bar_horizontal_name: str = TERMINAL_SCROLL_BAR_HORIZONTAL,
    vertical_policy: QtCore.Qt.ScrollBarPolicy = QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded,
    horizontal_policy: QtCore.Qt.ScrollBarPolicy = QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
) -> QtWidgets.QScrollArea:
    """为 QScrollArea 设置统一 objectName 与滚动条样式名。"""
    scroll.setObjectName(area_name)
    scroll.setVerticalScrollBarPolicy(vertical_policy)
    scroll.setHorizontalScrollBarPolicy(horizontal_policy)
    style_scroll_bar(scroll.verticalScrollBar(), orientation=QtCore.Qt.Orientation.Vertical, name=bar_vertical_name)
    style_scroll_bar(scroll.horizontalScrollBar(), orientation=QtCore.Qt.Orientation.Horizontal, name=bar_horizontal_name)
    return scroll


def frameless_scroll_area(
    content: QtWidgets.QWidget,
    *,
    area_name: str = TERMINAL_SCROLL_AREA,
    bar_vertical_name: str = TERMINAL_SCROLL_BAR_VERTICAL,
    bar_horizontal_name: str = TERMINAL_SCROLL_BAR_HORIZONTAL,
    vertical_policy: QtCore.Qt.ScrollBarPolicy = QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded,
    horizontal_policy: QtCore.Qt.ScrollBarPolicy = QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
) -> QtWidgets.QScrollArea:
    """无边框滚动区 + 高对比度滚动条。"""
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    scroll.setWidget(content)
    return style_scroll_area(
        scroll,
        area_name=area_name,
        bar_vertical_name=bar_vertical_name,
        bar_horizontal_name=bar_horizontal_name,
        vertical_policy=vertical_policy,
        horizontal_policy=horizontal_policy,
    )


def style_table_scroll_bars(
    view: QtWidgets.QAbstractScrollArea,
    *,
    vertical_name: str = TERMINAL_SCROLL_BAR_VERTICAL,
    horizontal_name: str = TERMINAL_SCROLL_BAR_HORIZONTAL,
) -> None:
    """为 QTableWidget / QTableView / QPlainTextEdit 等绑定滚动条样式名。"""
    style_scroll_bar(view.verticalScrollBar(), orientation=QtCore.Qt.Orientation.Vertical, name=vertical_name)
    style_scroll_bar(view.horizontalScrollBar(), orientation=QtCore.Qt.Orientation.Horizontal, name=horizontal_name)


def style_market_table_scroll_bars(view: QtWidgets.QAbstractScrollArea) -> None:
    style_scroll_bar(
        view.verticalScrollBar(),
        orientation=QtCore.Qt.Orientation.Vertical,
        name=MARKET_TABLE_SCROLL_BAR,
    )
