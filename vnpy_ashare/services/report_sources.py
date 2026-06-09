"""研报数据源（问小达 MCP 不可用时的 Tushare 降级）。

由 AnalysisService 调用；``ANALYSIS_REPORT_FALLBACK`` 环境变量控制是否启用。
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

from vnpy.trader.constant import Exchange


def report_fallback_enabled() -> bool:
    """是否启用 Tushare research_report 降级（默认启用）。"""
    value = (os.getenv("ANALYSIS_REPORT_FALLBACK") or "tushare").strip().lower()
    return value not in {"0", "false", "off", "none", "no"}


def to_ts_code(symbol: str, exchange) -> str:
    """A 股代码 + Exchange → Tushare ts_code。"""
    value = getattr(exchange, "value", str(exchange)).upper()
    name = getattr(exchange, "name", str(exchange)).upper()
    if value in {"SSE", "SH"} or name == "SSE":
        return f"{symbol}.SH"
    if value in {"SZSE", "SZ"} or name == "SZSE":
        return f"{symbol}.SZ"
    if value in {"BSE", "BJ"} or name == "BSE":
        return f"{symbol}.BJ"
    if symbol.startswith(("5", "6", "9")):
        return f"{symbol}.SH"
    if symbol.startswith(("0", "3")):
        return f"{symbol}.SZ"
    return f"{symbol}.BJ"


def fetch_tushare_reports(symbol: str, exchange: Exchange, *, limit: int = 10) -> dict[str, Any]:
    """拉取近一年研报；返回 ``{reports, warnings, source?}``。"""
    from vnpy_ashare.screener.tushare_client import TushareNotConfiguredError, get_tushare_pro

    try:
        pro = get_tushare_pro()
    except TushareNotConfiguredError as ex:
        return {"reports": [], "warnings": [str(ex)]}

    ts_code = to_ts_code(symbol, exchange)
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    try:
        frame = pro.research_report(ts_code=ts_code, start_date=start, end_date=end)
    except Exception as ex:
        return {"reports": [], "warnings": [f"Tushare research_report 调用失败：{ex}"]}

    if frame is None or frame.empty:
        return {
            "reports": [],
            "warnings": [f"Tushare 未返回 {ts_code} 近一年研报"],
        }

    reports: list[dict[str, Any]] = []
    for _, row in frame.head(limit).iterrows():
        reports.append(
            {
                "title": str(row.get("report_title") or row.get("title") or "研报"),
                "broker": str(row.get("org_name") or row.get("broker") or ""),
                "date": str(row.get("report_date") or row.get("pub_date") or ""),
                "rating": str(row.get("rating") or row.get("report_type") or ""),
                "summary": str(row.get("abstract") or row.get("report_content") or "")[:2000],
                "source": "tushare",
                "tool": "research_report",
            }
        )
    return {
        "reports": reports,
        "source": "tushare",
        "warnings": [] if reports else [f"Tushare 未返回 {ts_code} 近一年研报"],
    }
