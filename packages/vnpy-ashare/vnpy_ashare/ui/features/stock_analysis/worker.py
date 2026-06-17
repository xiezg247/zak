"""个股分析后台 Worker（按 Tab 分 scope 懒加载）。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore

from vnpy_ashare.services.stock_analysis import (
    StockAnalysisPayload,
    StockAnalysisScope,
    StockAnalysisService,
)

__all__ = [
    "StockAnalysisPayload",
    "StockAnalysisScope",
    "StockAnalysisService",
    "StockAnalysisWorker",
]


class StockAnalysisWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        vt_symbol: str,
        scope: StockAnalysisScope,
        stock_analysis_service: StockAnalysisService,
        quote_summary: dict[str, Any] | None = None,
        sync_financials: bool = False,
        stock_name: str = "",
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.vt_symbol = vt_symbol
        self.scope = scope
        self.stock_analysis_service = stock_analysis_service
        self.quote_summary = quote_summary or {}
        self.sync_financials = sync_financials
        self.stock_name = stock_name

    def run(self) -> None:
        try:
            payload = self.stock_analysis_service.load_scope(
                self.vt_symbol,
                self.scope,
                quote_summary=self.quote_summary,
                sync_financials=self.sync_financials,
                stock_name=self.stock_name,
            )
            self.finished.emit(payload)
        except Exception as ex:
            self.failed.emit(str(ex))
