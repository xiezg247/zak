"""TeamOrchestrator：并行调度子 Agent + chief 汇总。"""

from __future__ import annotations

import concurrent.futures
import json
import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from vnpy_common.ai.access import get_ai_context
from vnpy_llm.chat.client import LlmClientError, StreamCancelled
from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.graph.agents.base import build_agent_system_prompt
from vnpy_llm.graph.runner import _conversation_dicts, _stream_agent
from vnpy_llm.graph.state import AGENT_STREAM_LABELS, AgentName, GraphStreamContext
from vnpy_llm.graph.team_symbol import resolve_team_symbol

AGENT_TIMEOUT_SECONDS = 60
MIN_COMPLETED_AGENTS = 2
SUB_AGENT_MAX_ROUNDS = 3
SUB_AGENT_PREFETCH_ROUNDS = 1
CHIEF_MAX_ROUNDS = 2

TEAM_AGENT_TOOLS: dict[AgentName, frozenset[str]] = {
    "financial": frozenset({"analyze_financial", "get_quote_context"}),
    "risk": frozenset({"analyze_risk", "get_bars_summary", "get_ashare_fear_greed_index"}),
    "strategy": frozenset({"technical_snapshot", "list_strategy_signals", "get_bars_summary"}),
}

TEAM_AGENTS: tuple[AgentName, ...] = ("financial", "risk", "strategy")

_JSON_BLOCK_PATTERN = re.compile(r"```json\s*\{.*?\}\s*```", re.DOTALL)


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


def _strip_json_blocks(text: str) -> str:
    return _JSON_BLOCK_PATTERN.sub("", text).strip()


def _prefetch_ready(data: dict[str, Any] | None) -> bool:
    return bool(data) and not data.get("error")


def _build_agent_task_spec(
    agent: AgentName,
    symbol: str,
    graph_ctx: GraphStreamContext,
) -> AgentTaskSpec:
    prefetch = graph_ctx.team_prefetch or {}
    scores = graph_ctx.team_scores or {}
    data = prefetch.get(agent)
    rule = scores.get(agent) or {}

    if _prefetch_ready(data if isinstance(data, dict) else None):
        user_content = (
            f"请对 {symbol} 做你负责维度的分析。\n\n"
            "【已预取数据 — 请勿重复调用工具，直接解读以下 JSON】\n"
            f"{json.dumps(data, ensure_ascii=False)}\n\n"
            "【规则评分参考（可微调但需说明理由）】\n"
            f"score={rule.get('score')}；{rule.get('summary', '')}\n\n"
            "输出 Markdown 分析过程，末尾用 ```json 代码块输出 "
            '{"score": 整数, "summary": "...", "highlights": [], "risks": []}。'
        )
        return AgentTaskSpec(
            user_msg={"role": "user", "content": user_content},
            use_tools=False,
            max_rounds=SUB_AGENT_PREFETCH_ROUNDS,
        )

    user_content = (
        f"请对 {symbol} 做你负责维度的分析。"
        f'必须先调用工具获取真实数据（symbol="{symbol}"），'
        "再输出 Markdown 分析过程，最后在 ```json 代码块中输出结构化评分。"
    )
    return AgentTaskSpec(
        user_msg={"role": "user", "content": user_content},
        use_tools=True,
        max_rounds=SUB_AGENT_MAX_ROUNDS,
    )


def _run_single_agent(
    agent: AgentName,
    conversation: list[dict[str, Any]],
    task: AgentTaskSpec,
    all_tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
    config: LlmConfig,
    graph_ctx: GraphStreamContext,
    should_cancel: Callable[[], bool] | None,
) -> AgentResult:
    result = AgentResult(agent=agent)
    try:
        tools = _filter_tools_for_team_agent(agent, all_tools) if task.use_tools else []
        system = build_agent_system_prompt(agent, graph_ctx)
        agent_messages = [{"role": "system", "content": system}, *conversation, task.user_msg]

        chunks: list[str] = []
        for delta in _stream_agent(
            config,
            agent_messages,
            tools,
            tool_executor,
            max_rounds=task.max_rounds,
            should_cancel=should_cancel,
        ):
            chunks.append(delta)

        result.markdown = "".join(chunks)
        result.json_data = _extract_json_from_text(result.markdown)
    except StreamCancelled:
        result.error = "用户取消"
        raise
    except Exception as ex:
        result.error = str(ex)

    return result


def _build_team_context_for_chief(
    results: dict[AgentName, AgentResult],
    context_text: str,
    team_scores: dict[str, Any] | None,
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
        parts.append(
            "\n【规则评分参考（加权综合参考分）】\n"
            + json.dumps(team_scores, ensure_ascii=False)
        )

    if context_text.strip():
        parts.append(f"\n【行情上下文】\n{context_text.strip()}")

    parts.append(
        "\n请综合子分析师结论与规则评分，生成综合研判。"
        "综合加权：财务 35% + 风险 25% + 策略 20% + 行情 20%。"
        "禁止编造未出现的数据。"
    )
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
    mode = "预取完成，解读模式" if graph_ctx.team_prefetch else "工具模式"
    return (
        f"\n🔄 分析团队已启动（{mode}）\n"
        f"标的：**{symbol}** | 规则参考分：财务 {fin} / 风险 {risk} / 策略 {strat} "
        f"| 加权 {weighted}\n\n"
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
) -> Iterator[str]:
    """团队并行分析入口。"""
    del max_rounds  # 各 Agent 使用 AgentTaskSpec 中的轮次

    if not config.configured:
        raise LlmClientError("未配置 LLM_API_KEY，请在 .env 中设置")

    symbol = _resolve_symbol(graph_ctx)
    if not symbol:
        raise LlmClientError(
            "未识别到股票代码。请指定代码（如 /team 600519 或「全面分析 002230.SZSE」），"
            "或在看盘页选中标的后说「全面分析这只票」。"
        )

    full_tools = all_tools or tools
    conversation = _conversation_dicts(messages)

    yield _format_prefetch_banner(graph_ctx, symbol)

    task_specs = {agent: _build_agent_task_spec(agent, symbol, graph_ctx) for agent in TEAM_AGENTS}

    results: dict[AgentName, AgentResult] = {}
    pending: dict[concurrent.futures.Future[AgentResult], AgentName] = {}
    deadline = time.monotonic() + AGENT_TIMEOUT_SECONDS

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(TEAM_AGENTS)) as executor:
        for agent in TEAM_AGENTS:
            future = executor.submit(
                _run_single_agent,
                agent,
                conversation,
                task_specs[agent],
                full_tools,
                tool_executor,
                config,
                graph_ctx,
                should_cancel,
            )
            pending[future] = agent

        while pending:
            if should_cancel and should_cancel():
                for future in pending:
                    future.cancel()
                raise StreamCancelled("用户已停止生成")

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            done, _ = concurrent.futures.wait(
                pending.keys(),
                timeout=min(remaining, 0.5),
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            if not done:
                continue

            for future in done:
                agent = pending.pop(future)
                try:
                    result = future.result(timeout=0)
                except concurrent.futures.CancelledError:
                    result = AgentResult(agent=agent, error="已取消")
                except Exception as ex:
                    result = AgentResult(agent=agent, error=str(ex))

                results[agent] = result
                label = AGENT_STREAM_LABELS.get(agent, agent)
                if result.error:
                    yield f"\n**{label}** ⚠️ 分析异常：{result.error}\n\n"
                else:
                    yield f"\n## {label}\n\n"
                    yield result.markdown
                    yield "\n"

    for agent in TEAM_AGENTS:
        if agent not in results:
            results[agent] = AgentResult(agent=agent, timed_out=True)
            label = AGENT_STREAM_LABELS.get(agent, agent)
            yield f"\n**{label}** ⏱️ 分析超时\n\n"

    completed = sum(
        1 for r in results.values() if not r.error and not r.timed_out and r.markdown.strip()
    )
    if completed < MIN_COMPLETED_AGENTS:
        yield (
            f"\n⚠️ 分析团队完成率不足（{completed}/{len(TEAM_AGENTS)}），"
            "无法生成综合研判。请稍后重试。\n"
        )
        return

    yield "\n---\n\n## 综合研判\n\n"

    chief_context = _build_team_context_for_chief(
        results,
        graph_ctx.context_text,
        graph_ctx.team_scores,
    )
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
            max_rounds=CHIEF_MAX_ROUNDS,
            should_cancel=should_cancel,
        ):
            yield delta
    except StreamCancelled:
        raise
    except Exception as ex:
        raise LlmClientError(f"综合研判生成失败: {ex}") from ex
