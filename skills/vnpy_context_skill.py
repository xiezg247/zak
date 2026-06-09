"""zak 终端上下文 Skill：当前选中标的与页面状态。"""

from __future__ import annotations

import json

from vnpy_skills.base import SkillTemplate, ToolSpec


class VnpyContextSkill(SkillTemplate):
    skill_name = "vnpy-context"
    author = "zak"
    description = "读取 zak 终端当前页面与选中标的上下文"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="get_quote_context",
                description=("获取终端当前页面与选中标的上下文（页面名、代码、行情摘要）。用户问「当前这只」「我选中的」时优先调用。"),
                parameters={"type": "object", "properties": {}},
            ),
        ]

    def get_quote_context(self) -> str:
        quote_service = self._services.get("quote")
        if quote_service is None:
            return json.dumps(
                {"message": "终端上下文服务未就绪"},
                ensure_ascii=False,
            )
        ctx = quote_service.get_current_context()
        payload: dict = {
            "page": ctx.page,
            "symbol": ctx.symbol,
            "exchange": ctx.exchange,
            "name": ctx.name,
            "quote_summary": ctx.quote_summary,
            "extra": ctx.extra,
            "text": ctx.to_text(),
        }
        if not ctx.symbol and not ctx.page:
            payload["message"] = "终端尚未推送选中标的，请用户在看盘页选中股票后再问"
        return json.dumps(payload, ensure_ascii=False)
