"""选股筛选 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.base import SkillTemplate, ToolSpec


class VnpyScreeningSkill(SkillTemplate):
    skill_name = "vnpy-screening"
    author = "zak"
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
                description="按指定条件筛选标的，返回符合条件的前N只股票",
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
        from vnpy_ashare.ai.session_context import get_market_quotes_cache

        quotes = get_market_quotes_cache()
        if not quotes:
            return json.dumps(
                {
                    "message": (
                        "暂无可用的市场行情数据。请先在终端打开「市场」页加载行情，"
                        "然后再次尝试选股。"
                    ),
                },
                ensure_ascii=False,
            )

        svc = self._get_screening_service()
        results = svc.screen_by_condition(name, quotes, top_n=int(top_n or 10))

        if not results:
            return json.dumps(
                {
                    "message": f"选股条件「{name}」未匹配到标的，可用的条件：涨幅榜、换手率排行、成交量放大",
                    "count": 0,
                },
                ensure_ascii=False,
            )

        summary = []
        for r in results:
            summary.append({
                "symbol": r.get("symbol", ""),
                "name": r.get("name", ""),
                "vt_symbol": r.get("vt_symbol", ""),
                "last_price": r.get("last_price"),
                "change_pct": r.get("change_pct"),
                "turnover_rate": r.get("turnover_rate"),
            })

        return json.dumps(
            {
                "condition": name,
                "count": len(summary),
                "results": summary,
            },
            ensure_ascii=False,
        )
