"""股票分析 Skill（诊断、技术形态、选股上下文）。"""

from __future__ import annotations

import json

from vnpy_skills.base import SkillTemplate, ToolSpec


class VnpyAnalysisSkill(SkillTemplate):
    skill_name = "vnpy-analysis"
    author = "zak"
    description = "股票诊断、技术形态、选股结果解读（数据来自本地 K 线与通达信 MCP）"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="diagnose_stock",
                description=(
                    "对单只股票做综合诊断：本地 K 线技术形态 + 通达信 MCP 研报/F10。"
                    "用户问「诊断」「基本面+技术面」「券商怎么看」时优先调用。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 600519.SSE",
                        },
                        "include_reports": {
                            "type": "boolean",
                            "description": "是否查询研报，默认 true",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            ToolSpec(
                name="technical_snapshot",
                description="查询本地 K 线的均线排列、区间涨跌、量比等技术面快照",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码"},
                        "lookback": {
                            "type": "integer",
                            "description": "回看 K 线根数，默认 60",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            ToolSpec(
                name="get_screening_context",
                description=(
                    "获取选股结果（当前 session 或指定 run_id）。"
                    "batch_top_n>0 时对前几只批量返回 technical_snapshot 摘要。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "run_id": {
                            "type": "string",
                            "description": "选股历史 run id（可选，来自选股页历史侧栏）",
                        },
                        "batch_top_n": {
                            "type": "integer",
                            "description": "对前 N 只（最多 10）附加技术面快照，默认 0",
                        },
                    },
                },
            ),
            ToolSpec(
                name="list_strategy_signals",
                description=(
                    "查询指定策略在本地 K 线上的规则信号（如双均线金叉/死叉、当前均线排列）。"
                    "用户问「双均线什么状态」「有没有金叉」时调用；禁止编造信号。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码"},
                        "class_name": {
                            "type": "string",
                            "description": "策略类名，默认 AshareDoubleMaStrategy",
                        },
                        "lookback": {
                            "type": "integer",
                            "description": "回看 K 线根数，默认 120",
                        },
                        "fast_window": {
                            "type": "integer",
                            "description": "快线周期，默认 10",
                        },
                        "slow_window": {
                            "type": "integer",
                            "description": "慢线周期，默认 20",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            ToolSpec(
                name="historical_pattern_summary",
                description=(
                    "历史区间走势统计（涨跌幅、波动、形态标签），用于回答「最近走势如何」。"
                    "仅描述历史，禁止包装成未来预测。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码"},
                        "lookback": {
                            "type": "integer",
                            "description": "统计区间 K 线根数，默认 20",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
        ]

    def _get_analysis_service(self):
        svc = self._services.get("analysis")
        if svc is None:
            raise RuntimeError("AnalysisService 未就绪")
        return svc

    def diagnose_stock(self, symbol: str, include_reports: bool = True) -> str:
        svc = self._get_analysis_service()
        result = svc.diagnose(symbol, include_reports=bool(include_reports))
        return json.dumps(result, ensure_ascii=False)

    def technical_snapshot(self, symbol: str, lookback: int = 60) -> str:
        svc = self._get_analysis_service()
        result = svc.technical_snapshot(symbol, lookback=int(lookback or 60))
        return json.dumps(result, ensure_ascii=False)

    def get_screening_context(self, run_id: str = "", batch_top_n: int = 0) -> str:
        svc = self._get_analysis_service()
        result = svc.build_screening_context(
            run_id=run_id.strip() or None,
            batch_top_n=int(batch_top_n or 0),
        )
        return json.dumps(result, ensure_ascii=False)

    def list_strategy_signals(
        self,
        symbol: str,
        class_name: str = "AshareDoubleMaStrategy",
        lookback: int = 120,
        fast_window: int = 10,
        slow_window: int = 20,
    ) -> str:
        svc = self._get_analysis_service()
        result = svc.strategy_signals(
            symbol,
            class_name=class_name or "AshareDoubleMaStrategy",
            lookback=int(lookback or 120),
            fast_window=int(fast_window or 10),
            slow_window=int(slow_window or 20),
        )
        return json.dumps(result, ensure_ascii=False)

    def historical_pattern_summary(self, symbol: str, lookback: int = 20) -> str:
        svc = self._get_analysis_service()
        result = svc.historical_pattern_summary(symbol, lookback=int(lookback or 20))
        return json.dumps(result, ensure_ascii=False)
