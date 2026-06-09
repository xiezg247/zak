"""两阶段意图路由：分类 → 工具子集 + 结构化提示。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from vnpy_llm.config import LlmConfig
from vnpy_llm.intent import (
    BacktestIntent,
    IntentAnalysis,
    IntentCategory,
    IntentRoute,
    ScreeningIntent,
)

AGENT_TOOL_NAMES = frozenset({
    "read_skill_file",
    "run_python",
    "list_skill_files",
})

TOOL_GROUPS: dict[IntentCategory, frozenset[str]] = {
    "general": frozenset(),
    "quote": frozenset({
        "get_quote_context",
        "get_bars_summary",
        "get_bars_data",
    }),
    "technical": frozenset({
        "get_quote_context",
        "get_bars_summary",
        "get_bars_data",
        "technical_snapshot",
        "list_strategy_signals",
        "historical_pattern_summary",
    }),
    "diagnosis": frozenset({
        "get_quote_context",
        "diagnose_stock",
    }),
    "screening": frozenset({
        "list_screeners",
        "propose_screening",
        "get_screening_context",
    }),
    "backtest": frozenset({
        "list_strategies",
        "get_backtest_result",
        "list_backtest_history",
        "list_strategy_signals",
    }),
    "watchlist": frozenset({
        "get_watchlist",
        "add_to_watchlist",
        "remove_from_watchlist",
        "get_quote_context",
    }),
    "data": frozenset({
        "get_bars_summary",
        "get_bars_data",
        "read_skill_file",
        "run_python",
        "list_skill_files",
    }),
}

PAGE_CATEGORY_HINT: dict[str, IntentCategory] = {
    "选股": "screening",
    "策略回测": "backtest",
    "回测对比": "backtest",
    "自选": "watchlist",
    "市场": "quote",
    "本地": "quote",
}

_CLASSIFY_PROMPT = """你是 zak 量化终端的意图分类器。根据用户最新一条消息，判断其主要意图类别。

类别说明：
- quote：当前价格、涨跌、选中标的行情
- technical：技术面、均线、量比、走势形态、策略信号（双均线等）
- diagnosis：个股综合诊断、研报、评级、F10、券商观点
- screening：选股、筛选、涨幅榜、换手率等条件选股
- backtest：回测结果、策略列表、历史回测对比
- watchlist：自选池增删查
- data：财务、宏观、需 Tushare/TickFlow 等外部数据接口
- general：闲聊、概念解释、与上述无关

若 category 为 screening，必须填写 screening 字段（intent 必填）。
若 category 为 backtest，必须填写 backtest 字段。
confidence=low 表示意图模糊，需要主对话追问。"""


@dataclass(frozen=True)
class RouteContext:
    """路由结果与过滤后的工具。"""

    analysis: IntentAnalysis
    tools: list[dict[str, Any]]
    routing_hint: str


def filter_tools_by_route(
    all_tools: list[dict[str, Any]],
    category: IntentCategory,
    *,
    mcp_tool_names: frozenset[str] | set[str] | None = None,
) -> list[dict[str, Any]]:
    """按意图类别过滤 OpenAI tools；general 或未知时返回全集。"""
    if not all_tools:
        return []
    if category == "general":
        return list(all_tools)

    allowed = set(TOOL_GROUPS.get(category, frozenset()))
    allowed.update(AGENT_TOOL_NAMES)

    mcp_names = mcp_tool_names or frozenset()
    if category == "diagnosis":
        allowed.update(name for name in mcp_names if name.startswith("mcp_"))
    if category == "data":
        allowed.update(name for name in mcp_names)

    if not allowed:
        return list(all_tools)

    filtered: list[dict[str, Any]] = []
    for tool in all_tools:
        fn = tool.get("function") or {}
        name = fn.get("name", "")
        if name in allowed:
            filtered.append(tool)

    return filtered if filtered else list(all_tools)


def build_routing_hint(analysis: IntentAnalysis, *, page: str = "") -> str:
    """生成注入 system 的路由提示。"""
    route = analysis.route
    lines = [
        "【本轮意图路由】",
        f"类别：{route.category}（置信度 {route.confidence}）",
    ]
    if route.reasoning:
        lines.append(f"判断：{route.reasoning}")
    if page:
        lines.append(f"当前页面：{page}")

    if analysis.screening and route.category == "screening":
        s = analysis.screening
        lines.append("【选股结构化解析】")
        lines.append(f"- intent: {s.intent}")
        if s.preset:
            lines.append(f"- preset: {s.preset}")
        lines.append(f"- top_n: {s.top_n}")
        if s.scheme_name:
            lines.append(f"- scheme_name: {s.scheme_name}")
        lines.append(f"- confidence: {s.confidence}")
        if s.clarification_needed:
            lines.append("- 意图不够明确，请先向用户追问，勿调用 propose_screening")
        elif s.confidence in ("high", "medium"):
            lines.append(
                "- 请调用 propose_screening，并传入上述 intent/preset/top_n 等参数"
            )

    if analysis.backtest and route.category == "backtest":
        b = analysis.backtest
        lines.append("【回测结构化解析】")
        lines.append(f"- action: {b.action}")
        if b.strategy_hint:
            lines.append(f"- strategy_hint: {b.strategy_hint}")
        lines.append(f"- history_limit: {b.history_limit}")
        tool_map = {
            "query_result": "get_backtest_result",
            "list_strategies": "list_strategies",
            "list_history": "list_backtest_history",
            "interpret_signals": "list_strategy_signals",
        }
        suggested = tool_map.get(b.action)
        if suggested:
            lines.append(f"- 建议优先调用：{suggested}")

    if route.confidence == "low" and route.category != "general":
        lines.append("置信度较低：可先简短追问澄清，再决定是否调用工具。")

    group = TOOL_GROUPS.get(route.category)
    if group:
        names = sorted(group | AGENT_TOOL_NAMES)
        lines.append(f"本轮可用工具子集：{', '.join(names)}")

    return "\n".join(lines)


def _keyword_fallback(user_text: str, page: str) -> IntentAnalysis | None:
    """API 不可用时的轻量规则兜底。"""
    text = user_text.strip()
    lower = text.lower()

    if any(k in text for k in ("选股", "筛选", "涨幅榜", "换手率", "涨最多")):
        return IntentAnalysis(
            route=IntentRoute(category="screening", confidence="medium", reasoning="关键词匹配"),
            screening=ScreeningIntent(intent=text, confidence="medium"),
        )
    if any(k in text for k in ("回测", "夏普", "最大回撤", "策略列表")):
        action = "list_history" if "历史" in text or "对比" in text else "query_result"
        if "有哪些策略" in text or "策略列表" in text:
            action = "list_strategies"
        return IntentAnalysis(
            route=IntentRoute(category="backtest", confidence="medium", reasoning="关键词匹配"),
            backtest=BacktestIntent(action=action, confidence="medium"),
        )
    if any(k in text for k in ("诊断", "研报", "评级", "券商")):
        return IntentAnalysis(
            route=IntentRoute(category="diagnosis", confidence="medium", reasoning="关键词匹配"),
        )
    if any(k in text for k in ("均线", "金叉", "死叉", "技术面", "形态")):
        return IntentAnalysis(
            route=IntentRoute(category="technical", confidence="medium", reasoning="关键词匹配"),
        )
    if page and page in PAGE_CATEGORY_HINT:
        cat = PAGE_CATEGORY_HINT[page]
        return IntentAnalysis(
            route=IntentRoute(category=cat, confidence="low", reasoning=f"页面上下文 {page}"),
        )
    if any(k in lower for k in ("多少钱", "涨了多少", "当前价")):
        return IntentAnalysis(
            route=IntentRoute(category="quote", confidence="medium", reasoning="关键词匹配"),
        )
    return None


def _structured_parse(config: LlmConfig, messages: list[dict[str, str]], model_type: type) -> Any:
    from vnpy_llm.client import LlmClientError, create_openai_client

    client = create_openai_client(config)
    try:
        response = client.beta.chat.completions.parse(
            model=config.model,
            messages=messages,
            response_format=model_type,
            max_tokens=1024,
            temperature=0.1,
        )
    except Exception as ex:
        raise LlmClientError(str(ex)) from ex

    message = response.choices[0].message
    parsed = getattr(message, "parsed", None)
    if parsed is not None:
        return parsed

    raw = message.content or ""
    if not raw.strip():
        raise LlmClientError("结构化解析返回空内容")
    return model_type.model_validate(json.loads(raw))


def analyze_user_intent(
    config: LlmConfig,
    user_text: str,
    *,
    page: str = "",
) -> IntentAnalysis:
    """结构化意图分析（分类 + 域内字段）。"""
    if not config.configured:
        fallback = _keyword_fallback(user_text, page)
        if fallback:
            return fallback
        return IntentAnalysis(route=IntentRoute(category="general", confidence="low"))

    page_hint = f"\n当前用户所在页面：{page}" if page else ""
    messages = [
        {"role": "system", "content": _CLASSIFY_PROMPT + page_hint},
        {"role": "user", "content": user_text.strip()},
    ]

    try:
        analysis: IntentAnalysis = _structured_parse(config, messages, IntentAnalysis)
    except Exception:
        fallback = _keyword_fallback(user_text, page)
        if fallback:
            return fallback
        return IntentAnalysis(route=IntentRoute(category="general", confidence="low"))

    if page and analysis.route.confidence == "low":
        boosted = PAGE_CATEGORY_HINT.get(page)
        if boosted and analysis.route.category == "general":
            analysis = analysis.model_copy(
                update={"route": analysis.route.model_copy(update={"category": boosted})},
            )

    if analysis.route.category == "screening" and analysis.screening is None:
        analysis = analysis.model_copy(
            update={"screening": ScreeningIntent(intent=user_text.strip(), confidence="medium")},
        )
    if analysis.route.category == "backtest" and analysis.backtest is None:
        analysis = analysis.model_copy(
            update={"backtest": BacktestIntent(confidence="medium")},
        )

    return analysis


def build_route_context(
    config: LlmConfig,
    user_text: str,
    all_tools: list[dict[str, Any]],
    *,
    page: str = "",
    mcp_tool_names: frozenset[str] | set[str] | None = None,
) -> RouteContext:
    """完整路由：分析意图 → 过滤工具 → 生成提示。"""
    analysis = analyze_user_intent(config, user_text, page=page)
    category = analysis.route.category
    if analysis.route.confidence == "low" and category != "general":
        tools = list(all_tools)
    else:
        tools = filter_tools_by_route(all_tools, category, mcp_tool_names=mcp_tool_names)

    hint = build_routing_hint(analysis, page=page)
    return RouteContext(analysis=analysis, tools=tools, routing_hint=hint)
