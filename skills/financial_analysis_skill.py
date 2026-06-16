"""财务深度分析 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.domain import SkillTemplate, ToolSpec


class FinancialAnalysisSkill(SkillTemplate):
    skill_name = "tdx-financial-analysis"
    author = "zak"
    description = "单票财务深度分析（PE/ROE/毛利率/现金流/杜邦）"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="analyze_financial",
                description=(
                    "对单只股票做财务深度分析。返回盈利能力（ROE/毛利率/净利率/扣非净利润同比）、"
                    "成长性（营收/利润 CAGR 近3年）、估值（PE(TTM)/PB/PS 与行业均值对比）、"
                    "偿债能力（资产负债率/流动比率）。用户问「财务面」「PE ROE」「盈利质量」时优先调用。"
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
