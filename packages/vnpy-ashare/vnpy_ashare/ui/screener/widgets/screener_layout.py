"""选股页主布局常量。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

# 左侧配置区（方案 + 硬过滤）
SCREENER_CONFIG_MIN_WIDTH = 320
SCREENER_CONFIG_DEFAULT_WIDTH = 380

# 右侧结果区
SCREENER_RESULT_MIN_WIDTH = 480


def apply_screener_main_splitter(splitter: QtWidgets.QSplitter, *, config_width: int | None = None) -> None:
    """配置主 Splitter：左栏配置区默认更宽，且随窗口适度拉伸。"""
    width = config_width or SCREENER_CONFIG_DEFAULT_WIDTH
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 2)
    splitter.setSizes([width, max(SCREENER_RESULT_MIN_WIDTH, 1000 - width)])


def configure_screener_config_column(column: QtWidgets.QWidget) -> None:
    column.setMinimumWidth(SCREENER_CONFIG_MIN_WIDTH)
