"""选股筛选 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.base import SkillTemplate, ToolSpec


class VnpyScreeningSkill(SkillTemplate):
    skill_name = "vnpy-screening"
    author = "vnpy_zak"
    description = "按条件筛选标的（涨幅榜、换手率、成交量等）"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="list_screeners",
                description="列出所有可用的选股条件",
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="screen_by_condition",
                description="按指定条件筛选标的",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "选股条件名称：涨幅榜 / 换手率排行 / 成交量放大",
                        },
                        "top_n": {
                            "type": "integer",
                            "description": "返回前 N 条，默认 10",
                        },
                    },
                    "required": ["name"],
                },
            ),
        ]

    def _get_screening_service(self):
        svc = self._services.get("screening")
        if svc is None:
            raise RuntimeError("ScreeningService 未就绪")
        return svc

    def list_screeners(self) -> str:
        svc = self._get_screening_service()
        names = svc.list_screeners()
        return json.dumps({"count": len(names), "screeners": names}, ensure_ascii=False)

    def screen_by_condition(self, name: str, top_n: int = 10) -> str:
        return json.dumps(
            {
                "message": (
                    f"选股条件「{name}」已就绪。"
                    "选股需要实时行情数据，请在市场涨幅页查看后，将你关注的标的告诉我来帮你分析。"
                ),
            },
            ensure_ascii=False,
        )
