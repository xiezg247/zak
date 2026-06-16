"""LangGraph 流式 runner：多 Agent 编排 + handoff。

编排流程（单轮用户消息）：
1. Supervisor 根据 IntentAnalysis 选定 target_agent，并按关键词追加 handoff_agents
2. 对每个 Agent：拼装 system prompt → 绑定域内工具 → create_agent ReAct 流式输出
3. handoff 时把上一 Agent 回复注入对话，并输出段标题（AGENT_STREAM_LABELS）

工具可见性 = filter_tools_for_agent（按 Specialist）∩ route_ctx.tools（意图路由收窄）。
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, cast

from langchain_core.messages import AIMessageChunk

from vnpy_llm.chat.client import LlmClientError, StreamCancelled
from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.graph.agents import (  # noqa: F401
    backtest,
    build_agent_system_prompt,  # noqa: F401 — 注册 agent prompts
    chief,
    data,
    financial,
    general,
    market,
    research,
    risk,
    screening,
    strategy,
)
from vnpy_llm.graph.messages import dict_messages_to_langchain
from vnpy_llm.graph.state import (
    AGENT_STREAM_LABELS,
    MAX_HANDOFFS,
    AgentName,
    GraphStreamContext,
    SupervisorDecision,
)
from vnpy_llm.graph.supervisor import build_supervisor_decision, filter_tools_for_agent
from vnpy_llm.graph.tool_utils import openai_tool_name
from vnpy_llm.graph.workflow import build_agent_graph
from vnpy_llm.routing.intent import IntentAnalysis

# LangGraph 默认 recursion_limit=25；旧公式 max_rounds*2+2 在 5 轮时仅 12，复杂 ReAct 易触顶
DEFAULT_MAX_TOOL_ROUNDS = 5
MIN_GRAPH_RECURSION_LIMIT = 25


def _recursion_limit_for_rounds(max_rounds: int) -> int:
    """按 tool 轮次估算 super-step 上限（每轮 model+tools 约 2–3 步）。"""
    return max(max_rounds * 4 + 8, MIN_GRAPH_RECURSION_LIMIT)


def _conversation_dicts(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """去掉 system；LangGraph 每段 Agent 单独注入 system prompt。"""
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


def _resolve_agent_tools(
    agent: AgentName,
    route_tools: list[dict[str, Any]],
    full_tools: list[dict[str, Any]],
    *,
    analysis: IntentAnalysis,
    user_text: str,
    mcp_tool_names: frozenset[str] | set[str] | None,
) -> list[dict[str, Any]]:
    """Supervisor 域过滤 ∩ 本轮 route 工具子集。

    route_tools 为空（低置信追问）时直接返回 []，避免 general 等 Agent 绕过路由。
    """
    agent_tools = filter_tools_for_agent(
        agent,
        full_tools,
        analysis=analysis,
        user_text=user_text,
        mcp_tool_names=mcp_tool_names,
    )
    if not route_tools:
        return []
    route_names = {openai_tool_name(tool) for tool in route_tools}
    route_names.discard("")
    return [tool for tool in agent_tools if openai_tool_name(tool) in route_names]


def _handoff_section_marker(agent: AgentName) -> str:
    """handoff 第二段起插入 Markdown 标题，便于用户区分多 Agent 输出。"""
    label = AGENT_STREAM_LABELS.get(agent, "").strip()
    return f"\n\n**{label}**\n\n" if label else ""


def _append_handoff_turn(
    conversation: list[dict[str, Any]],
    prior_reply: str,
    handoff_context: str,
) -> list[dict[str, Any]]:
    """将上一 Agent 产出伪装为 assistant + 协作续接 user，供下一 Agent 续写。"""
    return [
        *conversation,
        {"role": "assistant", "content": prior_reply},
        {"role": "user", "content": f"【协作续接】{handoff_context}"},
    ]


def _stream_agent(
    config: LlmConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    *,
    max_rounds: int,
    should_cancel: Callable[[], bool] | None,
) -> Iterator[str]:
    """单 Agent 的 LangGraph ReAct 流；仅 yield 文本 delta。"""
    if not tools and not any(item.get("role") == "user" for item in messages):
        return

    lc_messages = dict_messages_to_langchain(messages)
    graph = build_agent_graph(config, tools, tool_executor)
    run_config = {"recursion_limit": _recursion_limit_for_rounds(max_rounds)}

    for item in graph.stream(
        {"messages": lc_messages},
        stream_mode="messages",
        config=cast(Any, run_config),
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


def _iter_agent_turn(
    *,
    index: int,
    agent: AgentName,
    agents_to_run: list[AgentName],
    decision: SupervisorDecision,
    graph_ctx: GraphStreamContext,
    conversation: list[dict[str, Any]],
    prior_reply: str,
    route_tools: list[dict[str, Any]],
    full_tools: list[dict[str, Any]],
    mcp_tool_names: frozenset[str] | set[str] | None,
    config: LlmConfig,
    tool_executor: Callable[[str, dict[str, Any]], str],
    max_rounds: int,
    should_cancel: Callable[[], bool] | None,
) -> Iterator[str]:
    """执行单个 Agent 段：可选 handoff 标题 → ReAct 流式输出。"""
    if index > 0:
        marker = _handoff_section_marker(agent)
        if marker:
            yield marker

    handoff_context = ""
    if index > 0:
        handoff_context = (
            f"{decision.handoff_reason}\n上一 Agent（{agents_to_run[index - 1]}）已回复：\n{prior_reply}\n请在此基础上补充你负责域内的分析，避免重复上文。"
        )

    agent_tools = _resolve_agent_tools(
        agent,
        route_tools,
        full_tools,
        analysis=graph_ctx.analysis,
        user_text=graph_ctx.user_text,
        mcp_tool_names=mcp_tool_names,
    )
    agent_messages = _build_agent_messages(
        graph_ctx,
        agent,
        conversation if index == 0 else _append_handoff_turn(conversation, prior_reply, handoff_context),
        handoff_context=handoff_context if index == 0 else "",
    )

    yield from _stream_agent(
        config,
        agent_messages,
        agent_tools,
        tool_executor,
        max_rounds=max_rounds,
        should_cancel=should_cancel,
    )


def stream_with_tools(
    config: LlmConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    *,
    max_rounds: int = DEFAULT_MAX_TOOL_ROUNDS,
    should_cancel: Callable[[], bool] | None = None,
    graph_ctx: GraphStreamContext,
    all_tools: list[dict[str, Any]] | None = None,
    mcp_tool_names: frozenset[str] | set[str] | None = None,
    on_handoff: Callable[[AgentName, AgentName, str], None] | None = None,
) -> Iterator[str]:
    """LangGraph 多 Agent 流式 tool loop（唯一有工具对话入口）。"""
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

            chunks: list[str] = []
            for delta in _iter_agent_turn(
                index=index,
                agent=agent,
                agents_to_run=agents_to_run,
                decision=decision,
                graph_ctx=graph_ctx,
                conversation=conversation,
                prior_reply=prior_reply,
                route_tools=tools,
                full_tools=full_tools,
                mcp_tool_names=mcp_tool_names,
                config=config,
                tool_executor=tool_executor,
                max_rounds=max_rounds,
                should_cancel=should_cancel,
            ):
                chunks.append(delta)
                yield delta

            prior_reply = "".join(chunks).strip()
            if index == 0 and not decision.handoff_agents:
                break
            # 上一段无输出时跳过后续 handoff，避免空转
            if not prior_reply and index < len(agents_to_run) - 1:
                break
    except StreamCancelled:
        raise
    except LlmClientError:
        raise
    except Exception as ex:
        raise LlmClientError(str(ex)) from ex
