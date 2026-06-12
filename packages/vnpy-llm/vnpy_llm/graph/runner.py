"""LangGraph 流式 runner：多 Agent 编排 + handoff。"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from langchain_core.messages import AIMessageChunk

from vnpy_llm.chat.client import LlmClientError, StreamCancelled
from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.graph.agents import (  # noqa: F401
    backtest,
    build_agent_system_prompt,  # noqa: F401 — 注册 agent prompts
    data,
    general,
    market,
    research,
    screening,
)
from vnpy_llm.graph.messages import dict_messages_to_langchain
from vnpy_llm.graph.state import AGENT_STREAM_LABELS, MAX_HANDOFFS, AgentName, GraphStreamContext
from vnpy_llm.graph.supervisor import build_supervisor_decision, filter_tools_for_agent
from vnpy_llm.graph.workflow import build_react_agent


def _conversation_dicts(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """去掉 system，保留 user/assistant/tool 对话历史。"""
    return [item for item in messages if item.get("role") != "system"]


def _build_agent_messages(
    ctx: GraphStreamContext,
    agent: AgentName,
    conversation: list[dict[str, Any]],
    *,
    handoff_context: str = "",
) -> list[dict[str, Any]]:
    system = build_agent_system_prompt(agent, ctx, handoff_context=handoff_context)
    return [{"role": "system", "content": system}, *conversation]


def _tool_name(tool: dict[str, Any]) -> str:
    return str((tool.get("function") or {}).get("name", "")).strip()


def _resolve_agent_tools(
    agent: AgentName,
    route_tools: list[dict[str, Any]],
    full_tools: list[dict[str, Any]],
    *,
    analysis: GraphStreamContext,
    user_text: str,
    mcp_tool_names: frozenset[str] | set[str] | None,
) -> list[dict[str, Any]]:
    """Supervisor 按 Agent 过滤，并与本轮 route 工具子集取交集。"""
    agent_tools = filter_tools_for_agent(
        agent,
        full_tools,
        analysis=analysis.analysis,
        user_text=user_text,
        mcp_tool_names=mcp_tool_names,
    )
    if not route_tools:
        return []
    route_names = {_tool_name(tool) for tool in route_tools if _tool_name(tool)}
    return [tool for tool in agent_tools if _tool_name(tool) in route_names]


def _stream_agent(
    config: LlmConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    *,
    max_rounds: int,
    should_cancel: Callable[[], bool] | None,
) -> Iterator[str]:
    if not tools and not any(item.get("role") == "user" for item in messages):
        return

    lc_messages = dict_messages_to_langchain(messages)
    graph = build_react_agent(config, tools, tool_executor)
    run_config = {"recursion_limit": max(max_rounds * 2 + 2, 10)}

    for item in graph.stream(
        {"messages": lc_messages},
        stream_mode="messages",
        config=run_config,
    ):
        if should_cancel and should_cancel():
            raise StreamCancelled("用户已停止生成")
        if not isinstance(item, tuple) or len(item) < 1:
            continue
        message = item[0]
        if not isinstance(message, AIMessageChunk):
            continue
        content = message.content
        if isinstance(content, str) and content:
            yield content


def stream_with_tools(
    config: LlmConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    *,
    max_rounds: int = 5,
    should_cancel: Callable[[], bool] | None = None,
    graph_ctx: GraphStreamContext,
    all_tools: list[dict[str, Any]] | None = None,
    mcp_tool_names: frozenset[str] | set[str] | None = None,
    on_handoff: Callable[[AgentName, AgentName, str], None] | None = None,
) -> Iterator[str]:
    """LangGraph 多 Agent 流式 tool loop。"""
    if not config.configured:
        raise LlmClientError("未配置 LLM_API_KEY，请在 .env 中设置")

    try:
        decision = build_supervisor_decision(graph_ctx.analysis, graph_ctx.user_text)
        conversation = _conversation_dicts(messages)
        full_tools = all_tools or tools
        agents_to_run: list[AgentName] = [decision.target_agent, *decision.handoff_agents][: 1 + MAX_HANDOFFS]

        prior_reply = ""
        for index, agent in enumerate(agents_to_run):
            if should_cancel and should_cancel():
                raise StreamCancelled("用户已停止生成")

            if index > 0 and on_handoff is not None:
                on_handoff(agents_to_run[index - 1], agent, decision.handoff_reason)

            if index > 0:
                section = AGENT_STREAM_LABELS.get(agent, "").strip()
                if section:
                    yield f"\n\n**{section}**\n\n"

            agent_tools = _resolve_agent_tools(
                agent,
                tools,
                full_tools,
                analysis=graph_ctx,
                user_text=graph_ctx.user_text,
                mcp_tool_names=mcp_tool_names,
            )

            handoff_context = ""
            if index > 0:
                handoff_context = (
                    f"{decision.handoff_reason}\n"
                    f"上一 Agent（{agents_to_run[index - 1]}）已回复：\n{prior_reply}\n"
                    "请在此基础上补充你负责域内的分析，避免重复上文。"
                )

            agent_messages = _build_agent_messages(
                graph_ctx,
                agent,
                conversation if index == 0 else _append_handoff_turn(conversation, prior_reply, handoff_context),
                handoff_context=handoff_context if index == 0 else "",
            )

            chunks: list[str] = []
            for delta in _stream_agent(
                config,
                agent_messages,
                agent_tools,
                tool_executor,
                max_rounds=max_rounds,
                should_cancel=should_cancel,
            ):
                chunks.append(delta)
                yield delta
            prior_reply = "".join(chunks).strip()
            if index == 0 and not decision.handoff_agents:
                break
            if not prior_reply and index < len(agents_to_run) - 1:
                break
    except StreamCancelled:
        raise
    except LlmClientError:
        raise
    except Exception as ex:
        raise LlmClientError(str(ex)) from ex


def _append_handoff_turn(
    conversation: list[dict[str, Any]],
    prior_reply: str,
    handoff_context: str,
) -> list[dict[str, Any]]:
    return [
        *conversation,
        {"role": "assistant", "content": prior_reply},
        {"role": "user", "content": f"【协作续接】{handoff_context}"},
    ]
