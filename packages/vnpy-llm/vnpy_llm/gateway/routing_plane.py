"""意图路由平面：router + supervisor 对外一层。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.graph.state import SupervisorDecision
from vnpy_llm.graph.supervisor import build_supervisor_decision
from vnpy_llm.routing.router import RouteContext, build_route_context


@dataclass(frozen=True)
class RoutingDecision:
    """意图分类 + Supervisor 委派的合并结果。"""

    route_ctx: RouteContext
    supervisor: SupervisorDecision


class RoutingPlane:
    """将 router 与 supervisor 封装为单一路由入口。"""

    def route(
        self,
        config: LlmConfig,
        user_text: str,
        all_tools: list[dict[str, Any]],
        *,
        page: str,
        mcp_tool_names: frozenset[str] | set[str],
    ) -> RoutingDecision:
        route_ctx = build_route_context(
            config,
            user_text,
            all_tools,
            page=page,
            mcp_tool_names=mcp_tool_names,
        )
        supervisor = build_supervisor_decision(route_ctx.analysis, user_text)
        return RoutingDecision(route_ctx=route_ctx, supervisor=supervisor)
