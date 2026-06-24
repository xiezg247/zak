"""财务深度分析 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.domain.template import SkillTemplate, ToolSpec


class FinancialAnalysisSkill(SkillTemplate):
    skill_name = "tdx-financial-analysis"
    author = "zak"
    description = "单票财务深度分析（PE/ROE/毛利率/现金流/杜邦）"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="analyze_financial",
                description=(
                    "对单只股票做财务深度分析。返回盈利能力、成长性、估值、偿债能力。"
                    "用户问「财务面」「PE ROE」「盈利质量」「估值趋势」时优先调用；"
                    "本地有估值历史时终端自动展示 PE/PB 折线迷你图。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 600519.SSE 或 002230.SZSE",
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

    def analyze_financial(self, symbol: str) -> str:
        svc = self._get_analysis_service()
        result = svc.analyze_financial(symbol)
        return json.dumps(result, ensure_ascii=False)
