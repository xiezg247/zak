"""项目品牌与窗口标题。"""

from __future__ import annotations

import vnpy
from vnpy.trader.utility import TRADER_DIR

APP_NAME = "zak"
APP_DISPLAY_NAME = "A股量化终端"
QAPP_NAME = f"{APP_NAME} - {APP_DISPLAY_NAME}"


def window_title() -> str:
    return f"{APP_NAME} - {APP_DISPLAY_NAME} - {vnpy.__version__}   [{TRADER_DIR}]"
