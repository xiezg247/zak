"""TeamOrchestrator：并行调度子 Agent + chief 汇总。"""

from __future__ import annotations

import concurrent.futures
import json
import queue
import re
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Literal

from vnpy_common.ai.access import get_ai_context
from vnpy_llm.chat.client import LlmClientError, StreamCancelled
from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.graph.agents.base import build_agent_system_prompt
from vnpy_llm.graph.runner import _conversation_dicts, _stream_agent
from vnpy_llm.graph.state import AGENT_STREAM_LABELS, AgentName, GraphStreamContext
from vnpy_llm.graph.team_schema import TEAM_SCORE_JSON_INSTRUCTION, extract_agent_score
from vnpy_llm.graph.team_scoring import compute_team_scores
from vnpy_llm.graph.team_symbol import resolve_team_symbol

AGENT_TIMEOUT_SECONDS = 60
MIN_COMPLETED_AGENTS = 2
SUB_AGENT_MAX_ROUNDS = 3
SUB_AGENT_PREFETCH_ROUNDS = 1
CHIEF_MAX_ROUNDS = 2

SCORE_DIMENSION: dict[AgentName, str] = {
    "financial": "financial",
    "risk": "risk",
    "strategy": "strategy",
}

TeamTraceCallback = Callable[[str, str, dict[str, Any]], None]
TeamPrefetchProvider = Callable[[str], dict[str, Any]]

TEAM_AGENT_TOOLS: dict[AgentName, frozenset[str]] = {
    "financial": frozenset({"analyze_financial", "diagnose_stock", "get_quote_context"}),
    "risk": frozenset({"analyze_risk", "get_bars_summary", "get_ashare_fear_greed_index"}),
    "strategy": frozenset({"technical_snapshot", "list_strategy_signals", "get_bars_summary"}),
}

TEAM_AGENTS: tuple[AgentName, ...] = ("financial", "risk", "strategy")

_JSON_BLOCK_PATTERN = re.compile(r"```json\s*\{.*?\}\s*```", re.DOTALL)

StreamEventKind = Literal["delta", "done", "error"]


@dataclass
class AgentTaskSpec:
    user_msg: dict[str, Any]
    use_tools: bool
    max_rounds: int


@dataclass
class AgentResult:
    agent: AgentName
    markdown: str = ""
    json_data: dict[str, Any] | None = None
    error: str | None = None
    timed_out: bool = False


@dataclass
class AgentStreamEvent:
    agent: AgentName
    kind: StreamEventKind
    text: str = ""
    result: AgentResult | None = None


def _filter_tools_for_team_agent(
    agent: AgentName,
    all_tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    allowed = TEAM_AGENT_TOOLS.get(agent, frozenset())
    if not allowed:
        return []
    return [tool for tool in all_tools if (tool.get("function") or {}).get("name", "") in allowed]


def _normalize_score_json(text: str, agent: AgentName) -> dict[str, Any] | None:
    return extract_agent_score(text, SCORE_DIMENSION[agent])


def _strip_json_blocks(text: str) -> str:
    return _JSON_BLOCK_PATTERN.sub("", text).strip()


def _prefetch_ready(data: dict[str, Any] | None) -> bool:
    return data is not None and not data.get("error")


def _build_agent_task_spec(
    agent: AgentName,
    symbol: str,
    graph_ctx: GraphStreamContext,
) -> AgentTaskSpec:
    prefetch = graph_ctx.team_prefetch or {}
    scores = graph_ctx.team_scores or {}
    data = prefetch.get(agent)
    rule = scores.get(agent) or {}
    diagnose = prefetch.get("diagnose") or {}

    if _prefetch_ready(data if isinstance(data, dict) else None):
        diagnose_hint = ""
        if agent == "financial" and diagnose.get("available"):
            diagnose_hint = f"\n\n【问小达诊断参考（预取已含，勿重复调用 diagnose_stock）】\n{json.dumps(diagnose, ensure_ascii=False)}\n"
        user_content = (
            f"请对 {symbol} 做你负责维度的分析。\n\n"
            "【已预取数据 — 请勿重复调用工具，直接解读以下 JSON】\n"
            f"{json.dumps(data, ensure_ascii=False)}\n\n"
            "【规则评分参考（可微调但需说明理由）】\n"
            f"score={rule.get('score')}；{rule.get('summary', '')}\n"
            f"{diagnose_hint}\n"
            f"{TEAM_SCORE_JSON_INSTRUCTION}"
        )
        return AgentTaskSpec(
            user_msg={"role": "user", "content": user_content},
            use_tools=False,
            max_rounds=SUB_AGENT_PREFETCH_ROUNDS,
        )

    diagnose_tool_hint = ""
    if agent == "financial":
        diagnose_tool_hint = "财务面可优先 analyze_financial；若本地数据不足可补充调用 diagnose_stock（问小达 MCP）。"
    user_content = f'请对 {symbol} 做你负责维度的分析。必须先调用工具获取真实数据（symbol="{symbol}"），{diagnose_tool_hint}{TEAM_SCORE_JSON_INSTRUCTION}'
    return AgentTaskSpec(
        user_msg={"role": "user", "content": user_content},
        use_tools=True,
        max_rounds=SUB_AGENT_MAX_ROUNDS,
    )


def _run_single_agent_streaming(
    agent: AgentName,
    conversation: list[dict[str, Any]],
    task: AgentTaskSpec,
    all_tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    config: LlmConfig,
    graph_ctx: GraphStreamContext,
    should_cancel: Callable[[], bool] | None,
    event_queue: queue.Queue[AgentStreamEvent],
) -> None:
    """在 worker 线程中执行单 Agent，将 token delta 实时推入队列。"""
    result = AgentResult(agent=agent)
    chunks: list[str] = []
    try:
        tools = _filter_tools_for_team_agent(agent, all_tools) if task.use_tools else []
        system = build_agent_system_prompt(agent, graph_ctx)
        agent_messages = [{"role": "system", "content": system}, *conversation, task.user_msg]

        for delta in _stream_agent(
            config,
            agent_messages,
            tools,
            tool_executor,
            max_rounds=task.max_rounds,
            should_cancel=should_cancel,
        ):
            if should_cancel and should_cancel():
                raise StreamCancelled("用户已停止生成")
            chunks.append(delta)
            event_queue.put(AgentStreamEvent(agent, "delta", delta))

        result.markdown = "".join(chunks)
        result.json_data = _normalize_score_json(result.markdown, agent)
        event_queue.put(AgentStreamEvent(agent, "done", result=result))
    except StreamCancelled:
        result.error = "用户取消"
        result.markdown = "".join(chunks)
        event_queue.put(AgentStreamEvent(agent, "error", "用户取消", result=result))
        raise
    except Exception as ex:
        result.error = str(ex)
        result.markdown = "".join(chunks)
        event_queue.put(AgentStreamEvent(agent, "error", str(ex), result=result))


def _yield_agent_section_header(agent: AgentName, started: set[AgentName]) -> Iterator[str]:
    if agent in started:
        return
    started.add(agent)
    label = AGENT_STREAM_LABELS.get(agent, agent)
    yield f"\n## {label}\n\n"


def _build_team_context_for_chief(
    results: dict[AgentName, AgentResult],
    context_text: str,
    team_scores: dict[str, Any] | None,
    diagnose: dict[str, Any] | None = None,
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
            body = _strip_json_blocks(r.markdown)
            if r.json_data:
                parts.append(f"\n### {label}\n{body}\n\n结构化评分：{json.dumps(r.json_data, ensure_ascii=False)}")
            else:
                parts.append(f"\n### {label}\n{body or r.markdown}")

    if team_scores:
        parts.append("\n【规则评分参考（加权综合参考分）】\n" + json.dumps(team_scores, ensure_ascii=False))

    if diagnose and diagnose.get("available"):
        parts.append("\n【问小达诊断（diagnose_stock / MCP 参考）】\n" + json.dumps(diagnose, ensure_ascii=False))
    elif diagnose and diagnose.get("note"):
        parts.append(f"\n【问小达诊断】{diagnose['note']}")

    if context_text.strip():
        parts.append(f"\n【行情上下文】\n{context_text.strip()}")

    parts.append("\n请综合子分析师结论与规则评分，生成综合研判。综合加权：财务 35% + 风险 25% + 策略 20% + 行情 20%。禁止编造未出现的数据。")
    return "\n".join(parts)


def _resolve_symbol(graph_ctx: GraphStreamContext) -> str | None:
    ctx = get_ai_context()
    resolved = resolve_team_symbol(
        user_text=graph_ctx.user_text,
        context_symbol=ctx.symbol,
        context_exchange=ctx.exchange,
    )
    if resolved:
        return resolved
    prefetch = graph_ctx.team_prefetch or {}
    return prefetch.get("symbol")


def _format_prefetch_banner(graph_ctx: GraphStreamContext, symbol: str) -> str:
    scores = graph_ctx.team_scores or {}
    fin = scores.get("financial", {}).get("score", "-")
    risk = scores.get("risk", {}).get("score", "-")
    strat = scores.get("strategy", {}).get("score", "-")
    weighted = scores.get("weighted", "-")
    prefetch = graph_ctx.team_prefetch or {}
    diagnose = prefetch.get("diagnose") or {}
    mode = "预取完成，解读模式" if graph_ctx.team_prefetch else "工具模式"
    diag_note = ""
    if diagnose.get("available"):
        source = diagnose.get("source", "cache")
        diag_note = f" | 问小达：{source}"
    return (
        f"\n🔄 分析团队已启动（{mode}{diag_note}）\n"
        f"标的：**{symbol}** | 规则参考分：财务 {fin} / 风险 {risk} / 策略 {strat} "
        f"| 加权 {weighted}\n"
        f"⏳ 财务 / 风险 / 策略并行生成中（逐段流式输出）…\n\n"
    )


def stream_team_analysis(
    config: LlmConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    *,
    max_rounds: int = SUB_AGENT_MAX_ROUNDS,
    should_cancel: Callable[[], bool] | None = None,
    graph_ctx: GraphStreamContext,
    all_tools: list[dict[str, Any]] | None = None,
    prefetch_provider: TeamPrefetchProvider | None = None,
    on_team_trace: TeamTraceCallback | None = None,
) -> Iterator[str]:
    """团队并行分析入口（子 Agent token 级流式输出）。"""
    del max_rounds

    if not config.configured:
        raise LlmClientError("未配置 LLM_API_KEY，请在 .env 中设置")

    symbol = _resolve_symbol(graph_ctx)
    if not symbol:
        raise LlmClientError("未识别到股票代码。请指定代码（如 /team 600519 或「全面分析 002230.SZSE」），或在看盘页选中标的后说「全面分析这只票」。")

    active_ctx = graph_ctx
    if active_ctx.team_prefetch is None and prefetch_provider is not None:
        yield "\n⏳ 正在预取本地数据与问小达诊断（并行，不阻塞对话启动）…\n"
        if on_team_trace:
            on_team_trace("prefetch_start", "", {})
        try:
            prefetch = prefetch_provider(symbol)
            scores = compute_team_scores(prefetch)
            active_ctx = active_ctx.model_copy(update={"team_prefetch": prefetch, "team_scores": scores})
            if on_team_trace:
                on_team_trace(
                    "prefetch_done",
                    "",
                    {
                        "weighted": scores.get("weighted"),
                        "symbol": prefetch.get("symbol", symbol),
                        "team_scores": scores,
                        "team_prefetch": prefetch,
                    },
                )
        except Exception as ex:
            if on_team_trace:
                on_team_trace("prefetch_error", "", {"error": str(ex)})

    full_tools = all_tools or tools
    conversation = _conversation_dicts(messages)

    yield _format_prefetch_banner(active_ctx, symbol)

    task_specs = {agent: _build_agent_task_spec(agent, symbol, active_ctx) for agent in TEAM_AGENTS}
    event_queue: queue.Queue[AgentStreamEvent] = queue.Queue()
    results: dict[AgentName, AgentResult] = {}
    partial: dict[AgentName, list[str]] = defaultdict(list)
    started: set[AgentName] = set()
    pending_agents = set(TEAM_AGENTS)
    deadline = time.monotonic() + AGENT_TIMEOUT_SECONDS

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(TEAM_AGENTS)) as executor:
        futures = [
            executor.submit(
                _run_single_agent_streaming,
                agent,
                conversation,
                task_specs[agent],
                full_tools,
                tool_executor,
                config,
                active_ctx,
                should_cancel,
                event_queue,
            )
            for agent in TEAM_AGENTS
        ]

        agent_started_trace: set[AgentName] = set()

        try:
            while pending_agents:
                if should_cancel and should_cancel():
                    for future in futures:
                        future.cancel()
                    raise StreamCancelled("用户已停止生成")

                if time.monotonic() >= deadline:
                    for future in futures:
                        future.cancel()
                    break

                try:
                    event = event_queue.get(timeout=0.15)
                except queue.Empty:
                    if all(future.done() for future in futures):
                        break
                    continue

                label = AGENT_STREAM_LABELS.get(event.agent, event.agent)
                if event.kind == "delta":
                    if event.agent not in agent_started_trace:
                        agent_started_trace.add(event.agent)
                        if on_team_trace:
                            on_team_trace("agent_start", event.agent, {})
                    yield from _yield_agent_section_header(event.agent, started)
                    partial[event.agent].append(event.text)
                    yield event.text
                elif event.kind == "done" and event.result is not None:
                    results[event.agent] = event.result
                    pending_agents.discard(event.agent)
                    if on_team_trace:
                        score = (event.result.json_data or {}).get("score")
                        on_team_trace(
                            "agent_done",
                            event.agent,
                            {"score": score, "ok": True},
                        )
                    if event.agent in started:
                        yield "\n"
                elif event.kind == "error":
                    result = event.result or AgentResult(agent=event.agent, error=event.text)
                    results[event.agent] = result
                    pending_agents.discard(event.agent)
                    if on_team_trace:
                        on_team_trace("agent_done", event.agent, {"ok": False, "error": result.error})
                    if not result.markdown.strip() and result.error:
                        yield f"\n**{label}** ⚠️ 分析异常：{result.error}\n\n"
        except StreamCancelled:
            raise

        concurrent.futures.wait(futures, timeout=0)

    for agent in pending_agents:
        label = AGENT_STREAM_LABELS.get(agent, agent)
        markdown = "".join(partial[agent])
        results[agent] = AgentResult(agent=agent, timed_out=True, markdown=markdown)
        if markdown.strip() and agent not in started:
            yield from _yield_agent_section_header(agent, started)
            yield markdown
        yield f"\n**{label}** ⏱️ 分析超时\n\n"

    for agent in TEAM_AGENTS:
        if agent in results or agent in started:
            continue
        label = AGENT_STREAM_LABELS.get(agent, agent)
        results[agent] = AgentResult(agent=agent, timed_out=True)
        yield f"\n**{label}** ⏱️ 分析超时\n\n"

    completed = sum(1 for r in results.values() if not r.error and not r.timed_out and r.markdown.strip())
    if completed < MIN_COMPLETED_AGENTS:
        yield (f"\n⚠️ 分析团队完成率不足（{completed}/{len(TEAM_AGENTS)}），无法生成综合研判。请稍后重试。\n")
        return

    yield "\n---\n\n## 综合研判\n\n"

    chief_context = _build_team_context_for_chief(
        results,
        active_ctx.context_text,
        active_ctx.team_scores,
        (active_ctx.team_prefetch or {}).get("diagnose"),
    )
    chief_messages = [
        {"role": "system", "content": build_agent_system_prompt("chief", active_ctx)},
        *conversation,
        {"role": "user", "content": chief_context},
    ]

    try:
        yield from _stream_agent(
            config,
            chief_messages,
            [],
            tool_executor,
            max_rounds=CHIEF_MAX_ROUNDS,
            should_cancel=should_cancel,
        )
    except StreamCancelled:
        raise
    except Exception as ex:
        raise LlmClientError(f"综合研判生成失败: {ex}") from ex
