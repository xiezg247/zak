"""股票分析 Service（技术形态、诊断聚合、MCP 研报）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vnpy_ashare.app.engine import AshareEngine

from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
from vnpy_ashare.services.analysis.diagnose import DiagnoseAnalyzer
from vnpy_ashare.services.analysis.mcp_binding import McpBinding, McpExecute
from vnpy_ashare.services.analysis.reports import ReportsFetcher
from vnpy_ashare.services.analysis.technical import TechnicalAnalyzer
from vnpy_ashare.services.base import BaseService


class AnalysisService(BaseService):
    """聚合本地 K 线与通达信 MCP，产出结构化分析 JSON。"""

    def __init__(self, engine: AshareEngine) -> None:
        super().__init__(engine)
        self._mcp = McpBinding()
        self._technical = TechnicalAnalyzer(engine)
        self._diagnose = DiagnoseAnalyzer(self._mcp)
        self._reports = ReportsFetcher(self._mcp)

    def bind_mcp(
        self,
        execute_fn: McpExecute | None,
        tool_names: list[str] | None = None,
    ) -> None:
        self._mcp.execute = execute_fn
        self._mcp.tool_names = list(tool_names or [])

    def technical_snapshot(
        self,
        symbol: str,
        *,
        lookback: int = 60,
        scope: str = "daily",
    ) -> dict[str, Any]:
        return self._technical.technical_snapshot(symbol, lookback=lookback, scope=scope)

    def diagnose(
        self,
        symbol: str,
        *,
        lookback: int = 60,
        include_reports: bool = True,
    ) -> dict[str, Any]:
        return self._diagnose.diagnose(symbol, lookback=lookback, include_reports=include_reports)

    def strategy_signals(
        self,
        symbol: str,
        *,
        class_name: str = "AshareDoubleMaStrategy",
        lookback: int = 120,
        fast_window: int = 10,
        slow_window: int = 20,
        scope: str = "daily",
    ) -> dict[str, Any]:
        return self._technical.strategy_signals(
            symbol,
            class_name=class_name,
            lookback=lookback,
            fast_window=fast_window,
            slow_window=slow_window,
            scope=scope,
        )

    def signal_snapshot(
        self,
        symbol: str,
        *,
        class_name: str = "AshareDoubleMaStrategy",
        lookback: int = 120,
        fast_window: int = 10,
        slow_window: int = 20,
        scope: str = "daily",
    ) -> SignalSnapshot | None:
        return self._technical.signal_snapshot(
            symbol,
            class_name=class_name,
            lookback=lookback,
            fast_window=fast_window,
            slow_window=slow_window,
            scope=scope,
        )

    def batch_strategy_signals(
        self,
        symbols: list[str],
        *,
        class_name: str = "AshareDoubleMaStrategy",
        lookback: int = 120,
        fast_window: int = 10,
        slow_window: int = 20,
        scope: str = "daily",
    ) -> dict[str, SignalSnapshot]:
        return self._technical.batch_strategy_signals(
            symbols,
            class_name=class_name,
            lookback=lookback,
            fast_window=fast_window,
            slow_window=slow_window,
            scope=scope,
        )

    def historical_pattern_summary(
        self,
        symbol: str,
        *,
        lookback: int = 20,
        scope: str = "daily",
    ) -> dict[str, Any]:
        return self._technical.historical_pattern_summary(symbol, lookback=lookback, scope=scope)

    def build_screening_context(
        self,
        *,
        run_id: str | None = None,
        batch_top_n: int = 0,
    ) -> dict[str, Any]:
        return self._technical.build_screening_context(run_id=run_id, batch_top_n=batch_top_n)

    def build_screening_explanation(
        self,
        *,
        run_id: str | None = None,
        batch_top_n: int = 5,
    ) -> dict[str, Any]:
        return self._technical.build_screening_explanation(run_id=run_id, batch_top_n=batch_top_n)

    def set_diagnose_result(self, payload: dict[str, Any] | None) -> None:
        """写入最近一次诊断结果，供 AI Skill ``get_diagnose_context`` 读取。"""
        self._diagnose.set_diagnose_result(payload)

    def get_diagnose_result(self) -> dict[str, Any] | None:
        return self._diagnose.get_diagnose_result()

    def _pick_mcp_tool(self, keywords: tuple[str, ...]) -> str | None:
        return self._reports.pick_mcp_tool(keywords)
