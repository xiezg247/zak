"""策略回测 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.domain import SkillTemplate, ToolSpec


class VnpyBacktestSkill(SkillTemplate):
    skill_name = "vnpy-backtest"
    author = "zak"
    description = "可用策略列表、最近回测结果查询"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="list_strategies",
                description="列出所有可用的 A 股策略及其适用/不适用场景",
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="get_backtest_result",
                description="获取最近一次策略回测的摘要指标（收益、回撤、夏普等）",
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="list_backtest_history",
                description="列出最近几次回测摘要，用于历史对比",
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "返回条数，默认 10",
                        },
                    },
                },
            ),
        ]

    def _get_backtest_service(self):
        svc = self._services.get("backtest")
        if svc is None:
            raise RuntimeError("BacktestService 未就绪")
        return svc

    def list_strategies(self) -> str:
        svc = self._get_backtest_service()
        strategies = svc.list_strategies()
        return json.dumps(
            {"count": len(strategies), "strategies": strategies},
            ensure_ascii=False,
        )

    def get_backtest_result(self) -> str:
        svc = self._get_backtest_service()
        summary = svc.get_last_summary()
        if summary is None:
            return json.dumps(
                {
                    "message": "暂无回测结果，请先在策略回测页完成一次回测",
                },
                ensure_ascii=False,
            )
        return json.dumps(summary, ensure_ascii=False)

    def list_backtest_history(self, limit: int = 10) -> str:
        svc = self._get_backtest_service()
        rows = svc.list_recent_summaries(limit=max(1, min(limit, 50)))
        return json.dumps({"count": len(rows), "runs": rows}, ensure_ascii=False)
