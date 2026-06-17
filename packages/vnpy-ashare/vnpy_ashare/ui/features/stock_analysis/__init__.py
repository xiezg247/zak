"""个股分析（跨页：看盘 / 选股 / 雷达等）。"""

from __future__ import annotations

from typing import Any

__all__ = [
    "StockAnalysisDialog",
    "StockAnalysisHost",
    "StockAnalysisPayload",
    "StockAnalysisScope",
    "StockAnalysisWorker",
    "show_stock_analysis_dialog",
    "show_stock_analysis_from_quotes_page",
    "show_stock_analysis_vt_symbol",
    "wire_stock_analysis_context_menu",
]


def __getattr__(name: str) -> Any:
    if name == "StockAnalysisDialog":
        from vnpy_ashare.ui.features.stock_analysis.dialog import StockAnalysisDialog

        return StockAnalysisDialog
    if name == "StockAnalysisHost":
        from vnpy_ashare.ui.features.stock_analysis.host import StockAnalysisHost

        return StockAnalysisHost
    if name in {"StockAnalysisPayload", "StockAnalysisScope", "StockAnalysisWorker"}:
        from vnpy_ashare.ui.features.stock_analysis import worker as _mod

        return getattr(_mod, name)
    if name in {
        "show_stock_analysis_dialog",
        "show_stock_analysis_from_quotes_page",
        "show_stock_analysis_vt_symbol",
        "wire_stock_analysis_context_menu",
    }:
        from vnpy_ashare.ui.features.stock_analysis import open as _mod

        return getattr(_mod, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
