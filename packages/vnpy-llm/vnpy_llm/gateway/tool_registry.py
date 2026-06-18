"""Skill + MCP 工具注册与执行（Gateway 控制面子模块）。"""

from __future__ import annotations

import json
from typing import Any, cast

from vnpy.trader.engine import MainEngine

from vnpy_llm.tools.result import enrich_tool_result
from vnpy_llm.tools.status import ToolsStatusSnapshot, build_tools_status
from vnpy_mcp.app.engine import McpEngine
from vnpy_skills.app.engine import SkillEngine


class ToolRegistry:
    """统一 Skill / MCP 工具注册、执行与状态聚合。"""

    def __init__(self, main_engine: MainEngine) -> None:
        self._main_engine = main_engine
        ashare_engine = getattr(main_engine, "engines", {}).get("Ashare")
        services: dict[str, object] = {}
        if ashare_engine is not None and hasattr(ashare_engine, "bar_service"):
            services = {
                "bar": ashare_engine.bar_service,
                "quote": ashare_engine.quote_service,
                "backtest": ashare_engine.backtest_service,
                "screening": ashare_engine.screening_service,
                "watchlist": ashare_engine.watchlist_service,
                "position": ashare_engine.position_service,
                "note": ashare_engine.note_service,
                "analysis": ashare_engine.analysis_service,
                "sentiment": ashare_engine.sentiment_service,
            }
        self.skill_engine = SkillEngine(services=services)
        self.skill_engine.load_all()
        self._enabled_skills = self.skill_engine.init_skills()
        self.mcp_engine = McpEngine()
        self.mcp_engine.load_all()
        self._enabled_mcp = self.mcp_engine.init_providers()
        self.rebind_analysis_mcp()
        if ashare_engine is not None and hasattr(ashare_engine, "backtest_service"):
            ashare_engine.backtest_service.get_last_summary()

    def get_openai_tools(self) -> list[dict[str, Any]]:
        """仅暴露 Skill 工具；MCP 经 Skill/Service 内部调用。"""
        return cast(list[dict[str, Any]], self.skill_engine.get_openai_tools())

    def get_mcp_tool_names(self) -> frozenset[str]:
        return frozenset(spec.name for spec in self.mcp_engine.get_tool_specs())

    def execute(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        """执行工具，返回 (enriched_result, success)。"""
        result = ""
        success = True
        try:
            if name in self.get_mcp_tool_names():
                result = self.mcp_engine.execute_tool(name, arguments)
            else:
                result = self.skill_engine.execute_tool(name, arguments)
            return enrich_tool_result(result), True
        except Exception as ex:
            success = False
            result = enrich_tool_result(json.dumps({"error": str(ex)}, ensure_ascii=False))
            return result, success

    def get_tools_status(self) -> ToolsStatusSnapshot:
        return build_tools_status(self.skill_engine, self.mcp_engine)

    def reload_skills(self) -> list[str]:
        self._enabled_skills = self.skill_engine.reload_skills()
        return cast(list[str], self._enabled_skills)

    def reload_mcp(self) -> list[str]:
        self._enabled_mcp = self.mcp_engine.reload_providers()
        return cast(list[str], self._enabled_mcp)

    def reload_all(self) -> tuple[list[str], list[str]]:
        skills = self.reload_skills()
        mcp = self.reload_mcp()
        self.rebind_analysis_mcp()
        return skills, mcp

    def rebind_analysis_mcp(self) -> None:
        ashare_engine = getattr(self._main_engine, "engines", {}).get("Ashare")
        if ashare_engine is None or not hasattr(ashare_engine, "analysis_service"):
            return
        ashare_engine.analysis_service.bind_mcp(
            self.mcp_engine.execute_tool,
            [spec.name for spec in self.mcp_engine.get_tool_specs()],
        )

    def get_enabled_skills(self) -> list[str]:
        return list(self._enabled_skills)

    def get_enabled_mcp(self) -> list[str]:
        return list(self._enabled_mcp)
