"""投研团队：确定性数据预取与财务面聚合。"""

from __future__ import annotations

import concurrent.futures
from typing import TYPE_CHECKING, Any

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.storage.repositories.financial import FinancialSnapshotRow, list_snapshots

if TYPE_CHECKING:
    from vnpy_ashare.services.analysis_service import AnalysisService


def snapshot_row_to_dict(row: FinancialSnapshotRow) -> dict[str, Any]:
    return {
        "end_date": row.end_date,
        "revenue": row.revenue,
        "net_income": row.net_income,
        "basic_eps": row.basic_eps,
        "roe": row.roe,
        "gross_margin": row.gross_margin,
        "net_margin": row.net_margin,
        "debt_ratio": row.debt_ratio,
        "current_ratio": row.current_ratio,
        "revenue_yoy": row.revenue_yoy,
        "net_income_yoy": row.net_income_yoy,
        "roe_yoy": row.roe_yoy,
        "free_cashflow": row.free_cashflow,
    }


def lookup_daily_basic(vt_symbol: str) -> dict[str, Any] | None:
    """从 Tushare daily_basic 缓存查找单票估值。"""
    try:
        from vnpy_ashare.screener.data.data_source import fetch_daily_basic_with_fallback

        rows, trade_date = fetch_daily_basic_with_fallback()
    except Exception:
        return None

    for row in rows:
        if row.get("vt_symbol") == vt_symbol:
            return {
                "trade_date": trade_date,
                "close": row.get("close"),
                "pe": row.get("pe"),
                "pe_ttm": row.get("pe_ttm"),
                "pb": row.get("pb"),
                "ps": row.get("ps"),
                "total_mv": row.get("total_mv"),
                "circ_mv": row.get("circ_mv"),
                "turnover_rate": row.get("turnover_rate"),
                "volume_ratio": row.get("volume_ratio"),
            }
    return None


def build_financial_extras(ts_code: str, vt_symbol: str) -> dict[str, Any]:
    """合并本地财报快照与 daily_basic 估值。"""
    snapshots = list_snapshots(ts_code, limit=4)
    latest = snapshots[0] if snapshots else None
    valuation = lookup_daily_basic(vt_symbol)

    latest_dict = snapshot_row_to_dict(latest) if latest else None
    has_roe = latest_dict is not None and latest_dict.get("roe") is not None
    has_margin = latest_dict is not None and latest_dict.get("gross_margin") is not None
    has_yoy = latest_dict is not None and latest_dict.get("net_income_yoy") is not None
    has_debt = latest_dict is not None and latest_dict.get("debt_ratio") is not None
    has_pe = valuation is not None and valuation.get("pe_ttm") is not None

    return {
        "valuation": valuation,
        "latest_financials": latest_dict,
        "financial_history": [snapshot_row_to_dict(row) for row in snapshots],
        "data_availability": {
            "roe": has_roe,
            "gross_margin": has_margin,
            "net_profit_yoy": has_yoy,
            "revenue_cagr_3y": False,
            "debt_ratio": has_debt,
            "current_ratio": latest_dict is not None and latest_dict.get("current_ratio") is not None,
            "pe_ttm": has_pe,
            "pb": valuation is not None and valuation.get("pb") is not None,
        },
        "note": (
            "估值来自 Tushare daily_basic 缓存；"
            "财报指标来自本地 financial_snapshots（需先同步财报）。"
            if snapshots or valuation
            else "暂无本地财报与 daily_basic 缓存，仅提供 K 线覆盖。"
        ),
    }


def prefetch_team_facts(service: AnalysisService, symbol: str) -> dict[str, Any]:
    """并行预取财务 / 风险 / 策略三维度事实数据（无 LLM）。"""
    item = parse_stock_symbol(symbol)
    if item is None:
        return {"symbol": symbol, "error": f"无法解析代码: {symbol}"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_fin = executor.submit(service.analyze_financial, symbol)
        future_risk = executor.submit(service.analyze_risk, symbol)
        future_str = executor.submit(service.analyze_strategy, symbol)
        financial = future_fin.result()
        risk = future_risk.result()
        strategy = future_str.result()

    return {
        "symbol": item.vt_symbol,
        "name": item.name,
        "financial": financial,
        "risk": risk,
        "strategy": strategy,
    }
