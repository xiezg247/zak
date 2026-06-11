"""看盘右侧与表格附属面板。"""

from vnpy_ashare.ui.quotes.panels.depth import DepthPanel
from vnpy_ashare.ui.quotes.panels.diagnose import DiagnosePanel, format_diagnose_html
from vnpy_ashare.ui.quotes.panels.loading_overlay import MarketTableHost

__all__ = [
    "DepthPanel",
    "DiagnosePanel",
    "MarketTableHost",
    "format_diagnose_html",
]
