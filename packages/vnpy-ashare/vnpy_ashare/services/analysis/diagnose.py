"""个股综合诊断（通达信问小达 MCP + 研报降级）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context import get_diagnose_result, parse_stock_symbol, set_diagnose_result
from vnpy_ashare.services.analysis.mcp_binding import McpBinding
from vnpy_ashare.services.analysis.reports import ReportsFetcher
from vnpy_ashare.services.tdx_diagnose import run_tdx_diagnose


class DiagnoseAnalyzer:
    def __init__(self, mcp: McpBinding) -> None:
        self._mcp = mcp
        self._reports = ReportsFetcher(mcp)

    def diagnose(
        self,
        symbol: str,
        *,
        lookback: int = 60,
        include_reports: bool = True,
    ) -> dict[str, Any]:
        del lookback  # 诊断走通达信问小达，不依赖本地 K 线根数
        result = run_tdx_diagnose(
            symbol,
            mcp_execute=self._mcp.execute,
            tool_names=self._mcp.tool_names,
            include_reports=include_reports,
        )
        if not include_reports or result.get("error"):
            return result
        if result.get("reports"):
            return result
        return self._merge_report_fallback(symbol, result)

    def _merge_report_fallback(self, symbol: str, result: dict[str, Any]) -> dict[str, Any]:
        """问小达研报维度为空时，尝试研报专用 MCP 工具或 Tushare 降级。"""
        item = parse_stock_symbol(symbol)
        if item is None:
            return result

        bundle = self._reports.fetch_reports(item)
        reports = bundle.get("reports") or []
        warnings = list(result.get("warnings") or [])
        warnings.extend(bundle.get("warnings") or [])

        if reports:
            merged = dict(result)
            merged["reports"] = reports
            sources = list(merged.get("sources") or [])
            source = str(bundle.get("source") or "tdx_mcp")
            if source not in sources:
                sources.append(source)
            merged["sources"] = sources
            merged["warnings"] = warnings
            return merged

        warnings.append(
            "问小达未返回研报条目；研报专用 MCP 与 Tushare 降级均无数据。"
            "zak 终端无 F10 页面，勿引导用户打开 F10。"
        )
        merged = dict(result)
        merged["warnings"] = warnings
        merged["reports"] = []
        return merged

    @staticmethod
    def set_diagnose_result(payload: dict[str, Any] | None) -> None:
        set_diagnose_result(payload)

    @staticmethod
    def get_diagnose_result() -> dict[str, Any] | None:
        return get_diagnose_result()
