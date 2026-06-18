"""风险分析 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.domain.template import SkillTemplate, ToolSpec


class RiskAnalysisSkill(SkillTemplate):
    skill_name = "tdx-risk-analysis"
    author = "zak"
    description = "单票风险分析（波动率/回撤/Beta/行业风险/市场情绪）"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="analyze_risk",
                description=(
                    "对单只股票做风险画像分析。返回价格风险（年化波动率/最大回撤/下行标准差）、"
                    "系统性风险（Beta/与大盘相关性）、流动性风险（日均成交额/换手率）、"
                    "行业风险（所属行业近期表现）。用户问「风险」「波动」「回撤」时优先调用。"
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

    def analyze_risk(self, symbol: str) -> str:
        svc = self._get_analysis_service()
        result = svc.analyze_risk(symbol)
        return json.dumps(result, ensure_ascii=False)
