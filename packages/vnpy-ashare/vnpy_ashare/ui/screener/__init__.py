"""策略选股 / 自动选股 UI。

目录约定：
- ``pages/``：策略选股、自动选股页
- ``widgets/``：结果表、配方面板、运行侧栏
- ``dialogs/``：确认与批量对话框
- ``workers/``：选股后台 Worker
"""

from vnpy_ashare.ui.screener.dialogs import (
    show_recipe_confirm_dialog,
    show_reference_peer_dialog,
    show_screener_confirm_dialog,
)
from vnpy_ashare.ui.screener.pages import AutoScreenerPageWidget, ScreenerPageWidget

__all__ = [
    "AutoScreenerPageWidget",
    "ScreenerPageWidget",
    "show_recipe_confirm_dialog",
    "show_reference_peer_dialog",
    "show_screener_confirm_dialog",
]
