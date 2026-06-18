"""个股分析 Service：按 Tab scope 聚合技术面、基本面与 Tushare 扩展数据。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_common.domain.base import MutableModel
from vnpy_ashare.services.base import BaseService
from vnpy_ashare.domain.financial.bundle import FinancialBundle, FinancialSyncResult
from vnpy_ashare.domain.stock.concept import ConceptProfile
from vnpy_ashare.domain.stock.context import MoneyflowProfile
from vnpy_ashare.domain.stock.events import EventsProfile
from vnpy_ashare.domain.stock.holders import HolderProfile
from vnpy_ashare.domain.stock.overview import OverviewDashboard
from vnpy_ashare.domain.stock.profile import SectorProfile, ValuationProfile
from vnpy_ashare.services.stock.concept import build_concept_profile
from vnpy_ashare.services.stock.context import build_moneyflow_profile, compute_relative_returns
from vnpy_ashare.services.stock.events import build_events_profile
from vnpy_ashare.services.stock.holders import build_holder_profile
from vnpy_ashare.services.stock.overview_dashboard import build_overview_dashboard
from vnpy_ashare.services.stock.profile import (
    build_sector_profile,
    build_valuation_profile,
    sync_disclosure_calendar,
    sync_valuation_history,
)
from vnpy_ashare.storage.repositories.valuation import ValuationRow, list_valuation_history

if TYPE_CHECKING:
    pass

StockAnalysisScope = Literal["overview", "sector", "concept", "capital", "events", "holders", "financial"]


class StockAnalysisPayload(MutableModel):
    vt_symbol: str = Field(description="合约代码（含交易所）")
    scope: StockAnalysisScope = Field(default="overview", description="分析 Tab 范围")
    diagnose: dict[str, Any] = Field(default_factory=dict, description="诊断指标")
    technical: dict[str, Any] = Field(default_factory=dict, description="技术面摘要")
    financial_bundle: FinancialBundle | None = Field(default=None, description="财报数据包")
    financial_sync: FinancialSyncResult | None = Field(default=None, description="财报同步结果")
    sector: SectorProfile | None = Field(default=None, description="板块画像")
    valuation: ValuationProfile | None = Field(default=None, description="估值画像")
    moneyflow: MoneyflowProfile | None = Field(default=None, description="资金流画像")
    concept: ConceptProfile | None = Field(default=None, description="概念题材画像")
    events: EventsProfile | None = Field(default=None, description="事件日历画像")
    holders: HolderProfile | None = Field(default=None, description="股东结构画像")
    valuation_history: list[ValuationRow] = Field(default_factory=list, description="估值历史序列")
    relative_returns: dict[str, float | None] = Field(default_factory=dict, description="相对收益")
    overview_dashboard: OverviewDashboard | None = Field(default=None, description="概览仪表盘")
    quote_summary: dict[str, Any] = Field(default_factory=dict, description="行情摘要")
    warnings: list[str] = Field(default_factory=list, description="警告信息")


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
        payload.overview_dashboard = build_overview_dashboard(
            self.engine,
            payload.vt_symbol,
            technical=payload.technical,
        )

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
