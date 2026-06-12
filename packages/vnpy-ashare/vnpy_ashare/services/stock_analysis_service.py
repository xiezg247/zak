"""个股分析 Service：按 Tab scope 聚合技术面、基本面与 Tushare 扩展数据。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.services.base import BaseService
from vnpy_ashare.services.financial_service import FinancialBundle, FinancialSyncResult
from vnpy_ashare.services.stock import (
    build_concept_profile,
    build_events_profile,
    build_holder_profile,
    build_moneyflow_profile,
    build_sector_profile,
    build_valuation_profile,
    compute_relative_returns,
    sync_disclosure_calendar,
    sync_valuation_history,
)
from vnpy_ashare.services.stock.concept import ConceptProfile
from vnpy_ashare.services.stock.context import MoneyflowProfile
from vnpy_ashare.services.stock.events import EventsProfile
from vnpy_ashare.services.stock.holders import HolderProfile
from vnpy_ashare.services.stock.profile import SectorProfile, ValuationProfile
from vnpy_ashare.storage.repositories.valuation import ValuationRow, list_valuation_history

if TYPE_CHECKING:
    pass

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
    moneyflow: MoneyflowProfile | None = None
    concept: ConceptProfile | None = None
    events: EventsProfile | None = None
    holders: HolderProfile | None = None
    valuation_history: list[ValuationRow] = field(default_factory=list)
    relative_returns: dict[str, float | None] = field(default_factory=dict)
    quote_summary: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class StockAnalysisService(BaseService):
    """个股分析弹窗数据门面（委托 analysis / financial 与 stock 子模块）。"""

    def load_scope(
        self,
        vt_symbol: str,
        scope: StockAnalysisScope,
        *,
        quote_summary: dict[str, Any] | None = None,
        sync_financials: bool = False,
        stock_name: str = "",
    ) -> StockAnalysisPayload:
        payload = StockAnalysisPayload(
            vt_symbol=vt_symbol,
            scope=scope,
            quote_summary=quote_summary or {},
        )
        if scope == "overview":
            self._load_overview(payload)
        elif scope == "sector":
            self._load_sector(payload, stock_name=stock_name)
        elif scope == "concept":
            payload.concept = build_concept_profile(vt_symbol)
            if payload.concept.message and not payload.concept.concepts:
                if "未配置" not in payload.concept.message:
                    payload.warnings.append(payload.concept.message)
        elif scope == "capital":
            payload.moneyflow = build_moneyflow_profile(vt_symbol)
        elif scope == "events":
            payload.events = build_events_profile(vt_symbol)
        elif scope == "holders":
            payload.holders = build_holder_profile(vt_symbol)
            if payload.holders.message and not payload.holders.holders:
                if "未配置" not in payload.holders.message:
                    payload.warnings.append(payload.holders.message)
        elif scope == "financial":
            self._load_financial(payload, sync_financials=sync_financials)
        else:
            raise ValueError(f"未知 scope: {scope}")
        return payload

    def _load_overview(self, payload: StockAnalysisPayload) -> None:
        analysis = self.engine.analysis_service
        payload.technical = analysis.technical_snapshot(payload.vt_symbol)
        payload.relative_returns = compute_relative_returns(self.engine, payload.vt_symbol)

    def _load_sector(self, payload: StockAnalysisPayload, *, stock_name: str) -> None:
        payload.valuation = sync_valuation_history(payload.vt_symbol)
        if payload.valuation.message and not payload.valuation.synced:
            if "跳过" not in payload.valuation.message:
                payload.warnings.append(payload.valuation.message)
        elif not payload.valuation.history_days:
            payload.valuation = build_valuation_profile(payload.vt_symbol)

        item = parse_stock_symbol(payload.vt_symbol)
        if item is not None:
            payload.valuation_history = list_valuation_history(item.ts_code, limit=120)

        count, disclosure_message = sync_disclosure_calendar(payload.vt_symbol)
        payload.sector = build_sector_profile(payload.vt_symbol, name=stock_name)
        if disclosure_message and "无法解析" not in disclosure_message and count == 0:
            if "未配置" not in disclosure_message:
                payload.warnings.append(disclosure_message)

    def _load_financial(self, payload: StockAnalysisPayload, *, sync_financials: bool) -> None:
        financial = self.engine.financial_service
        if sync_financials:
            bundle, sync_result = financial.get_or_sync(payload.vt_symbol)
            payload.financial_bundle = bundle
            payload.financial_sync = sync_result
            if sync_result and sync_result.warnings:
                payload.warnings.extend(sync_result.warnings)
        else:
            payload.financial_bundle = financial.get_bundle(payload.vt_symbol)
