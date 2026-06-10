"""VeighNa 动态加载入口：ui 模块导出各页面 Widget。"""

from vnpy_ashare.ui.shell.page_shell import (
    LocalPageWidget,
    MarketPageWidget,
    QuotesShellWidget,
    WatchlistPageWidget,
)

__all__ = [
    "LocalPageWidget",
    "MarketPageWidget",
    "QuotesShellWidget",
    "WatchlistPageWidget",
]
