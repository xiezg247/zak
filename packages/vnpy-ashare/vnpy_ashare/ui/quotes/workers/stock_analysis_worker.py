"""个股分析后台 Worker（按 Tab 分 scope 懒加载）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from vnpy.trader.ui import QtCore

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
from vnpy_ashare.services.financial_service import FinancialBundle, FinancialSyncResult
from vnpy_ashare.services.stock_analysis_context import (
    MoneyflowProfile,
    build_moneyflow_profile,
    compute_relative_returns,
)
from vnpy_ashare.services.stock_concept_service import ConceptProfile, build_concept_profile
from vnpy_ashare.services.stock_events_service import EventsProfile, build_events_profile
from vnpy_ashare.services.stock_holder_service import HolderProfile, build_holder_profile
from vnpy_ashare.services.stock_profile_service import (
    SectorProfile,
    ValuationProfile,
    build_sector_profile,
    build_valuation_profile,
    sync_disclosure_calendar,
    sync_valuation_history,
)
from vnpy_ashare.storage.valuation_store import ValuationRow, list_valuation_history

StockAnalysisScope = Literal["overview", "sector", "concept", "capital", "events", "holders", "financial"]


@dataclass
class StockAnalysisPayload:
    vt_symbol: str
    scope: StockAnalysisScope = "overview"
    diagnose: dict[str, Any] = field(default_factory=dict)
    technical: dict[str, Any] = field(default_factory=dict)
    financial_bundle: FinancialBundle | None = None
    financial_sync: FinancialSyncResult | None = None
    sector: SectorProfile | None = None
    valuation: ValuationProfile | None = None
    signal: SignalSnapshot | None = None
    moneyflow: MoneyflowProfile | None = None
    concept: ConceptProfile | None = None
    events: EventsProfile | None = None
    holders: HolderProfile | None = None
    valuation_history: list[ValuationRow] = field(default_factory=list)
    relative_returns: dict[str, float | None] = field(default_factory=dict)
    quote_summary: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class StockAnalysisWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        vt_symbol: str,
        scope: StockAnalysisScope,
        analysis_service,
        financial_service,
        quote_summary: dict[str, Any] | None = None,
        sync_financials: bool = False,
        stock_name: str = "",
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.vt_symbol = vt_symbol
        self.scope = scope
        self.analysis_service = analysis_service
        self.financial_service = financial_service
        self.quote_summary = quote_summary or {}
        self.sync_financials = sync_financials
        self.stock_name = stock_name

    def run(self) -> None:
        payload = StockAnalysisPayload(
            vt_symbol=self.vt_symbol,
            scope=self.scope,
            quote_summary=self.quote_summary,
        )
        try:
            if self.scope == "overview":
                self._load_overview(payload)
            elif self.scope == "sector":
                self._load_sector(payload)
            elif self.scope == "concept":
                payload.concept = build_concept_profile(self.vt_symbol)
                if payload.concept.message and not payload.concept.concepts:
                    if "未配置" not in payload.concept.message:
                        payload.warnings.append(payload.concept.message)
            elif self.scope == "capital":
                payload.moneyflow = build_moneyflow_profile(self.vt_symbol)
            elif self.scope == "events":
                payload.events = build_events_profile(self.vt_symbol)
            elif self.scope == "holders":
                payload.holders = build_holder_profile(self.vt_symbol)
                if payload.holders.message and not payload.holders.holders:
                    if "未配置" not in payload.holders.message:
                        payload.warnings.append(payload.holders.message)
            elif self.scope == "financial":
                self._load_financial(payload)
            else:
                raise ValueError(f"未知 scope: {self.scope}")

            self.finished.emit(payload)
        except Exception as ex:
            self.failed.emit(str(ex))

    def _load_overview(self, payload: StockAnalysisPayload) -> None:
        if self.analysis_service is None:
            return
        payload.technical = self.analysis_service.technical_snapshot(self.vt_symbol)
        payload.signal = self.analysis_service.signal_snapshot(self.vt_symbol)
        engine = getattr(self.analysis_service, "_engine", None)
        payload.relative_returns = compute_relative_returns(engine, self.vt_symbol)
        if payload.signal is not None:
            payload.signal = self.analysis_service.enrich_relative_index(payload.signal)

    def _load_sector(self, payload: StockAnalysisPayload) -> None:
        payload.valuation = sync_valuation_history(self.vt_symbol)
        if payload.valuation.message and not payload.valuation.synced:
            if "跳过" not in payload.valuation.message:
                payload.warnings.append(payload.valuation.message)
        elif not payload.valuation.history_days:
            payload.valuation = build_valuation_profile(self.vt_symbol)

        item = parse_stock_symbol(self.vt_symbol)
        if item is not None:
            payload.valuation_history = list_valuation_history(item.ts_code, limit=120)

        _count, disclosure_message = sync_disclosure_calendar(self.vt_symbol)
        payload.sector = build_sector_profile(self.vt_symbol, name=self.stock_name)
        if disclosure_message and "无法解析" not in disclosure_message and _count == 0:
            if "未配置" not in disclosure_message:
                payload.warnings.append(disclosure_message)

    def _load_financial(self, payload: StockAnalysisPayload) -> None:
        if self.financial_service is None:
            return
        if self.sync_financials:
            bundle, sync_result = self.financial_service.get_or_sync(self.vt_symbol)
            payload.financial_bundle = bundle
            payload.financial_sync = sync_result
            if sync_result and sync_result.warnings:
                payload.warnings.extend(sync_result.warnings)
        else:
            payload.financial_bundle = self.financial_service.get_bundle(self.vt_symbol)
