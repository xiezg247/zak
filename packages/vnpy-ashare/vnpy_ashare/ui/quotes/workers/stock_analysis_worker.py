"""个股分析后台 Worker。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vnpy.trader.ui import QtCore

from vnpy_ashare.services.financial_service import FinancialBundle, FinancialSyncResult
from vnpy_ashare.services.stock_profile_service import (
    SectorProfile,
    ValuationProfile,
    build_sector_profile,
    build_valuation_profile,
    sync_disclosure_calendar,
    sync_valuation_history,
)


@dataclass
class StockAnalysisPayload:
    vt_symbol: str
    diagnose: dict[str, Any] = field(default_factory=dict)
    technical: dict[str, Any] = field(default_factory=dict)
    financial_bundle: FinancialBundle | None = None
    financial_sync: FinancialSyncResult | None = None
    sector: SectorProfile | None = None
    valuation: ValuationProfile | None = None
    quote_summary: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class StockAnalysisWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        vt_symbol: str,
        analysis_service,
        financial_service,
        quote_summary: dict[str, Any] | None = None,
        sync_financials: bool = True,
        stock_name: str = "",
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.vt_symbol = vt_symbol
        self.analysis_service = analysis_service
        self.financial_service = financial_service
        self.quote_summary = quote_summary or {}
        self.sync_financials = sync_financials
        self.stock_name = stock_name

    def run(self) -> None:
        payload = StockAnalysisPayload(vt_symbol=self.vt_symbol, quote_summary=self.quote_summary)
        try:
            if self.analysis_service is not None:
                payload.diagnose = self.analysis_service.diagnose(self.vt_symbol)
                payload.technical = self.analysis_service.technical_snapshot(self.vt_symbol)
            if self.financial_service is not None and self.sync_financials:
                bundle, sync_result = self.financial_service.get_or_sync(self.vt_symbol)
                payload.financial_bundle = bundle
                payload.financial_sync = sync_result
                if sync_result and sync_result.warnings:
                    payload.warnings.extend(sync_result.warnings)
            elif self.financial_service is not None:
                payload.financial_bundle = self.financial_service.get_bundle(self.vt_symbol)

            payload.valuation = sync_valuation_history(self.vt_symbol)
            if payload.valuation.message and not payload.valuation.synced:
                if "跳过" not in payload.valuation.message:
                    payload.warnings.append(payload.valuation.message)
            elif not payload.valuation.history_days:
                payload.valuation = build_valuation_profile(self.vt_symbol)

            _count, disclosure_message = sync_disclosure_calendar(self.vt_symbol)
            payload.sector = build_sector_profile(self.vt_symbol, name=self.stock_name)
            if disclosure_message and "无法解析" not in disclosure_message and _count == 0:
                if "未配置" not in disclosure_message:
                    payload.warnings.append(disclosure_message)

            self.finished.emit(payload)
        except Exception as ex:
            self.failed.emit(str(ex))
