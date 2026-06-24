"""Market Agent 编排：择时数据预取 + 单 Agent 流式解读。"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.graph.runner import stream_with_tools
from vnpy_llm.graph.state import GraphStreamContext

MARKET_PREFETCH_SPECS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("get_emotion_cycle", {}),
    ("get_ashare_fear_greed_index", {"include_components": False}),
)

_PREFETCH_LABELS: dict[str, str] = {
    "get_emotion_cycle": "情绪周期",
    "get_ashare_fear_greed_index": "恐贪指数",
}


def prefetch_market_facts(
    tool_executor: Callable[[str, dict[str, Any]], str],
) -> dict[str, str]:
    """同步预取择时三件套，供 Market Agent 首轮引用。"""
    payload: dict[str, str] = {}
    for name, arguments in MARKET_PREFETCH_SPECS:
        try:
            payload[name] = tool_executor(name, arguments)
        except Exception as ex:
            payload[name] = f'{{"error": "{ex}"}}'
    return payload


def format_market_prefetch_block(prefetch: dict[str, str]) -> str:
    lines = ["【Market 预取数据】（优先引用；用户未要求刷新时勿重复调用）"]
    for tool, raw in prefetch.items():
        label = _PREFETCH_LABELS.get(tool, tool)
        lines.append(f"### {label}")
        text = (raw or "").strip()
        if len(text) > 6000:
            text = text[:6000] + "\n...(预取结果过长已截断)"
        lines.append(text or "（空）")
    return "\n".join(lines)


def stream_market_analysis(
    config: LlmConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    *,
    should_cancel: Callable[[], bool] | None = None,
    graph_ctx: GraphStreamContext,
    all_tools: list[dict[str, Any]] | None = None,
    mcp_tool_names: frozenset[str] | set[str] | None = None,
    on_handoff: Callable[[str, str, str], None] | None = None,
) -> Iterator[str]:
    """Market 专用编排：预取情绪/恐贪后进入 ReAct 流式 loop。"""
    prefetch = prefetch_market_facts(tool_executor)
    block = format_market_prefetch_block(prefetch)
    merged_context = graph_ctx.context_text.strip()
    if merged_context:
        merged_context = f"{merged_context}\n\n{block}"
    else:
        merged_context = block
    active_ctx = graph_ctx.model_copy(
        update={
            "market_prefetch": prefetch,
            "context_text": merged_context,
        }
    )
    yield "\n📊 已预取情绪周期 / 恐贪指数…\n\n"
    yield from stream_with_tools(
        config,
        messages,
        tools,
        tool_executor,
        should_cancel=should_cancel,
        graph_ctx=active_ctx,
        all_tools=all_tools,
        mcp_tool_names=mcp_tool_names,
        on_handoff=on_handoff,
    )
