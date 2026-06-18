"""股票分析 Skill（诊断、技术形态、选股上下文）。"""

from __future__ import annotations

import json

from vnpy_skills.domain.template import SkillTemplate, ToolSpec


class VnpyAnalysisSkill(SkillTemplate):
    skill_name = "vnpy-analysis"
    author = "zak"
    description = "股票技术形态、策略信号、选股结果解读（诊断见 tdx-stock-diagnose）"

    def register_tools(self) -> list[ToolSpec]:
        return [
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
                name="explain_screening_run",
                description=("编排选股解读上下文：结果快照、板块分布、同配方与上次 diff、可选技术面 batch。解读选股结果时优先于 get_screening_context。"),
                parameters={
                    "type": "object",
                    "properties": {
                        "run_id": {
                            "type": "string",
                            "description": "选股历史 run id（可选）",
                        },
                        "batch_top_n": {
                            "type": "integer",
                            "description": "对前 N 只（最多 10）附加技术面快照，默认 5",
                        },
                    },
                },
            ),
            ToolSpec(
                name="get_screening_context",
                description=("获取选股结果（当前 session 或指定 run_id）。batch_top_n>0 时对前几只批量返回 technical_snapshot 摘要。"),
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
                name="list_watchlist_signal_panel",
                description=(
                    "批量查询自选页策略信号区名单的规则信号快照（最多 10 只）。用户问「扫一遍信号区」「信号区哪些值得关注」时调用；可含实时行情修饰。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "class_name": {
                            "type": "string",
                            "description": "策略类名，默认 AshareDoubleMaStrategy",
                        },
                        "fast_window": {
                            "type": "integer",
                            "description": "快线周期，默认 10",
                        },
                        "slow_window": {
                            "type": "integer",
                            "description": "慢线周期，默认 20",
                        },
                        "include_live_quote": {
                            "type": "boolean",
                            "description": "是否附带实时行情与盘中提示，默认 false",
                        },
                    },
                },
            ),
            ToolSpec(
                name="list_strategy_signals",
                description=(
                    "查询指定策略在本地 K 线上的规则信号（如双均线金叉/死叉、当前均线排列）。用户问「双均线什么状态」「有没有金叉」时调用；禁止编造信号。"
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
                    "历史区间走势统计（涨跌幅、波动、形态标签、当前连涨/连阴天数）。"
                    "本地日 K 优先；本地不足时自动降级问小达 MCP。"
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
            ToolSpec(
                name="trend_scenario_summary",
                description=(
                    "本地走势情景摘要：均线/量比、结构锚点（支撑/阻力）、统计参考带与方向提示。"
                    "用户问走势预测、5日情景、方向倾向、支撑压力时优先调用；"
                    "输出供 LLM 组织 bull/base/bear 情景分析，非确定性预测。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码"},
                        "horizon_days": {
                            "type": "integer",
                            "description": "情景展望交易日数，默认 5",
                        },
                        "lookback": {
                            "type": "integer",
                            "description": "技术面回看 K 线根数，默认 60",
                        },
                        "class_name": {
                            "type": "string",
                            "description": "策略类名（结构锚点），默认 AshareDoubleMaStrategy",
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
                name="evaluate_entry_mode",
                description=(
                    "评估单票更适合打板、半路还是低吸；结合涨跌幅、10cm/20cm、连板地位与情绪周期。用户问「这只能打板吗」「能不能追」「半路还是低吸」时调用。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码，如 600519.SSE"},
                    },
                    "required": ["symbol"],
                },
            ),
            ToolSpec(
                name="assess_regulatory_deviation",
                description=(
                    "评估监管异动距离：近 10 日涨停次数、10/30 日累计涨幅是否接近严重异动线。"
                    "用户问「会不会进监管」「异动距离」「10 日 4 涨停」时调用。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码，如 600519.SSE"},
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

    def technical_snapshot(self, symbol: str, lookback: int = 60) -> str:
        svc = self._get_analysis_service()
        result = svc.technical_snapshot(symbol, lookback=int(lookback or 60))
        return json.dumps(result, ensure_ascii=False)

    def explain_screening_run(self, run_id: str = "", batch_top_n: int = 5) -> str:
        svc = self._get_analysis_service()
        result = svc.build_screening_explanation(
            run_id=run_id.strip() or None,
            batch_top_n=int(batch_top_n or 5),
        )
        return json.dumps(result, ensure_ascii=False)

    def get_screening_context(self, run_id: str = "", batch_top_n: int = 0) -> str:
        svc = self._get_analysis_service()
        result = svc.build_screening_context(
            run_id=run_id.strip() or None,
            batch_top_n=int(batch_top_n or 0),
        )
        return json.dumps(result, ensure_ascii=False)

    def list_watchlist_signal_panel(
        self,
        class_name: str = "AshareDoubleMaStrategy",
        fast_window: int = 10,
        slow_window: int = 20,
        include_live_quote: bool = False,
    ) -> str:
        svc = self._get_analysis_service()
        result = svc.list_watchlist_signal_panel(
            class_name=class_name or "AshareDoubleMaStrategy",
            fast_window=int(fast_window or 10),
            slow_window=int(slow_window or 20),
            include_live_quote=bool(include_live_quote),
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

    def trend_scenario_summary(
        self,
        symbol: str,
        horizon_days: int = 5,
        lookback: int = 60,
        class_name: str = "AshareDoubleMaStrategy",
        fast_window: int = 10,
        slow_window: int = 20,
    ) -> str:
        svc = self._get_analysis_service()
        result = svc.trend_scenario_summary(
            symbol,
            horizon_days=int(horizon_days or 5),
            lookback=int(lookback or 60),
            class_name=class_name or "AshareDoubleMaStrategy",
            fast_window=int(fast_window or 10),
            slow_window=int(slow_window or 20),
        )
        return json.dumps(result, ensure_ascii=False)

    def evaluate_entry_mode(self, symbol: str) -> str:
        svc = self._get_analysis_service()
        result = svc.evaluate_entry_mode(symbol)
        return json.dumps(result, ensure_ascii=False)

    def assess_regulatory_deviation(self, symbol: str) -> str:
        svc = self._get_analysis_service()
        result = svc.assess_regulatory_deviation(symbol)
        return json.dumps(result, ensure_ascii=False)
