"""个股综合诊断（通达信问小达 MCP）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context import get_diagnose_result, set_diagnose_result
from vnpy_ashare.services.analysis.mcp_binding import McpBinding
from vnpy_ashare.services.tdx_diagnose import run_tdx_diagnose


class DiagnoseAnalyzer:
    def __init__(self, mcp: McpBinding) -> None:
        self._mcp = mcp

    def diagnose(
        self,
        symbol: str,
        *,
        lookback: int = 60,
        include_reports: bool = True,
    ) -> dict[str, Any]:
        del lookback  # 诊断改走通达信问小达，不再依赖本地 K 线根数
        return run_tdx_diagnose(
            symbol,
            mcp_execute=self._mcp.execute,
            tool_names=self._mcp.tool_names,
            include_reports=include_reports,
        )

    @staticmethod
    def set_diagnose_result(payload: dict[str, Any] | None) -> None:
        set_diagnose_result(payload)

    @staticmethod
    def get_diagnose_result() -> dict[str, Any] | None:
        return get_diagnose_result()
