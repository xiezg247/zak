"""通达信问小达个股诊断 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.domain import SkillTemplate, ToolSpec


class TdxDiagnoseSkill(SkillTemplate):
    skill_name = "tdx-stock-diagnose"
    author = "zak"
    description = "单票综合诊断（通达信问小达：行情、技术指标、财务、资金流）"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="diagnose_stock",
                description=(
                    "对单只股票做综合诊断，数据来自通达信问小达 MCP（非本地 K 线）。"
                    "覆盖行情、MACD/KDJ/RSI、PE/ROE、主力资金。"
                    "用户问「诊断」「这个票怎么样」「基本面+技术面」时优先调用。"
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

    def diagnose_stock(self, symbol: str) -> str:
        svc = self._get_analysis_service()
        result = svc.diagnose(symbol)
        return json.dumps(result, ensure_ascii=False)
