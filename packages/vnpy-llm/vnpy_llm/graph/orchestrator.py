"""TeamOrchestrator：并行调度子 Agent + chief 汇总。

编排流程：
1. 用户意图为 team_analysis → 从用户消息中提取 symbol
2. 并行提交 financial / risk / strategy 三个子 Agent 到 ThreadPoolExecutor
3. 主线程按完成顺序 yield 章节标题 + 流式输出
4. 收集结构化 JSON（末尾代码块提取）
5. 全部完成后启动 chief Agent 汇总
"""

from __future__ import annotations

import concurrent.futures
import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from vnpy_llm.chat.client import LlmClientError, StreamCancelled
from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.graph.agents.base import build_agent_system_prompt
from vnpy_llm.graph.runner import _conversation_dicts, _stream_agent
from vnpy_llm.graph.state import AGENT_STREAM_LABELS, AgentName, GraphStreamContext

AGENT_TIMEOUT_SECONDS = 30
MIN_COMPLETED_AGENTS = 2

_SYMBOL_PATTERN = re.compile(r"(\d{6}(?:\.(?:SSE|SZSE|SH|SZ))?)", re.IGNORECASE)

TEAM_AGENT_TOOLS: dict[AgentName, frozenset[str]] = {
    "financial": frozenset({"analyze_financial", "get_quote_context"}),
    "risk": frozenset({"analyze_risk", "get_bars_summary", "get_ashare_fear_greed_index"}),
    "strategy": frozenset({"technical_snapshot", "list_strategy_signals", "get_bars_summary"}),
}

TEAM_AGENTS: tuple[AgentName, ...] = ("financial", "risk", "strategy")


@dataclass
class AgentResult:
    agent: AgentName
    markdown: str = ""
    json_data: dict[str, Any] | None = None
    error: str | None = None
    timed_out: bool = False


def _extract_symbol(text: str) -> str | None:
    m = _SYMBOL_PATTERN.search(text)
    if not m:
        return None
    raw = m.group(1).upper()
    if raw.endswith(".SH"):
        raw = raw.replace(".SH", ".SSE")
    elif raw.endswith(".SZ") and not raw.endswith(".SZSE"):
        raw = raw.replace(".SZ", ".SZSE")
    if "." not in raw:
        raw = raw + ".SSE"
    return raw


def _filter_tools_for_team_agent(
    agent: AgentName,
    all_tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    allowed = TEAM_AGENT_TOOLS.get(agent, frozenset())
    if not allowed:
        return []
    return [
        tool for tool in all_tools
        if (tool.get("function") or {}).get("name", "") in allowed
    ]


def _extract_json_from_text(text: str) -> dict[str, Any] | None:
    pattern = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
    matches = pattern.findall(text)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def _run_single_agent(
    agent: AgentName,
    symbol: str,
    messages: list[dict[str, Any]],
    all_tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    config: LlmConfig,
    graph_ctx: GraphStreamContext,
    max_rounds: int,
    should_cancel: Callable[[], bool] | None,
) -> AgentResult:
    result = AgentResult(agent=agent)
    try:
        tools = _filter_tools_for_team_agent(agent, all_tools)
        system = build_agent_system_prompt(agent, graph_ctx)
        agent_messages = [{"role": "system", "content": system}, *messages]

        chunks: list[str] = []
        for delta in _stream_agent(
            config,
            agent_messages,
            tools,
            tool_executor,
            max_rounds=max_rounds,
            should_cancel=should_cancel,
        ):
            chunks.append(delta)

        result.markdown = "".join(chunks)
        result.json_data = _extract_json_from_text(result.markdown)
    except StreamCancelled:
        result.error = "用户取消"
    except Exception as ex:
        result.error = str(ex)

    return result


def _build_team_context_for_chief(
    results: dict[AgentName, AgentResult],
    context_text: str,
) -> str:
    parts = ["【子分析师输出】"]
    for agent_name in TEAM_AGENTS:
        r = results.get(agent_name)
        label = AGENT_STREAM_LABELS.get(agent_name, agent_name)
        if r is None:
            parts.append(f"\n### {label}\n（未执行）")
        elif r.error:
            parts.append(f"\n### {label}\n（异常：{r.error}）")
        elif r.timed_out:
            parts.append(f"\n### {label}\n（超时未完成）")
        else:
            parts.append(f"\n### {label}\n{r.markdown}")

    if context_text.strip():
        parts.append(f"\n【行情上下文】\n{context_text.strip()}")

    parts.append("\n请根据以上子分析师的输出和行情上下文，生成综合研判。")
    return "\n".join(parts)


def stream_team_analysis(
    config: LlmConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    *,
    max_rounds: int = 3,
    should_cancel: Callable[[], bool] | None = None,
    graph_ctx: GraphStreamContext,
    all_tools: list[dict[str, Any]] | None = None,
) -> Iterator[str]:
    """团队并行分析入口。"""
    if not config.configured:
        raise LlmClientError("未配置 LLM_API_KEY，请在 .env 中设置")

    symbol = _extract_symbol(graph_ctx.user_text)
    if not symbol:
        raise LlmClientError("未识别到股票代码，请提供如 /team 600519 或"全面分析 600519"")

    full_tools = all_tools or tools
    conversation = _conversation_dicts(messages)

    team_user_msg = {
        "role": "user",
        "content": f"请对 {symbol} 做你负责维度的分析，先输出 Markdown 分析过程，最后输出 JSON 结构。",
    }
    agent_messages = [*conversation, team_user_msg]

    names_str = "、".join(AGENT_STREAM_LABELS.get(a, a) for a in TEAM_AGENTS)
    yield f"\n🔄 分析团队已启动：{names_str}（并行分析中...）\n\n"

    results: dict[AgentName, AgentResult] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(TEAM_AGENTS)) as executor:
        future_map: dict[concurrent.futures.Future[AgentResult], AgentName] = {}
        for agent in TEAM_AGENTS:
            future = executor.submit(
                _run_single_agent,
                agent,
                symbol,
                agent_messages,
                full_tools,
                tool_executor,
                config,
                graph_ctx,
                max_rounds,
                should_cancel,
            )
            future_map[future] = agent

        for future in concurrent.futures.as_completed(future_map, timeout=AGENT_TIMEOUT_SECONDS):
            agent = future_map[future]
            try:
                result = future.result()
            except concurrent.futures.TimeoutError:
                result = AgentResult(agent=agent, timed_out=True)
            except Exception as ex:
                result = AgentResult(agent=agent, error=str(ex))

            results[agent] = result

            label = AGENT_STREAM_LABELS.get(agent, agent)
            if result.error:
                yield f"\n**{label}** ⚠️ 分析异常：{result.error}\n\n"
            elif result.timed_out:
                yield f"\n**{label}** ⏱️ 分析超时\n\n"
            else:
                yield f"\n## {label}\n\n"
                yield result.markdown
                yield "\n"

    for agent in TEAM_AGENTS:
        if agent not in results:
            results[agent] = AgentResult(agent=agent, timed_out=True)

    completed = sum(
        1 for r in results.values() if not r.error and not r.timed_out and r.markdown
    )
    if completed < MIN_COMPLETED_AGENTS:
        yield f"\n⚠️ 分析团队完成率不足（{completed}/{len(TEAM_AGENTS)}），无法生成综合研判。请稍后重试。\n"
        return

    yield "\n---\n"

    chief_context = _build_team_context_for_chief(results, graph_ctx.context_text)
    chief_messages = [
        {"role": "system", "content": build_agent_system_prompt("chief", graph_ctx)},
        *conversation,
        {"role": "user", "content": chief_context},
    ]

    try:
        for delta in _stream_agent(
            config,
            chief_messages,
            [],
            tool_executor,
            max_rounds=max_rounds,
            should_cancel=should_cancel,
        ):
            yield delta
    except StreamCancelled:
        raise
    except Exception as ex:
        raise LlmClientError(f"综合研判生成失败: {ex}") from ex
