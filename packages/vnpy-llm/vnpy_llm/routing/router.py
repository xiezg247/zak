"""两阶段意图路由：分类 → 工具子集 + 结构化提示。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from vnpy_llm.chat.client import LlmClientError, create_openai_client
from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.routing.intent import (
    BacktestIntent,
    IntentAnalysis,
    IntentCategory,
    IntentRoute,
    MarketEnrichment,
    ScreeningIntent,
)

AGENT_TOOL_NAMES = frozenset(
    {
        "read_skill_file",
        "run_python",
        "list_skill_files",
    }
)

FEAR_GREED_TOOL = "get_ashare_fear_greed_index"

TOOL_GROUPS: dict[IntentCategory, frozenset[str]] = {
    "general": frozenset(),
    "quote": frozenset(
        {
            "get_quote_context",
            "get_bars_summary",
            "get_bars_data",
        }
    ),
    "technical": frozenset(
        {
            "get_quote_context",
            "get_bars_summary",
            "get_bars_data",
            "technical_snapshot",
            "list_strategy_signals",
            "historical_pattern_summary",
        }
    ),
    "diagnosis": frozenset(
        {
            "get_quote_context",
            "diagnose_stock",
        }
    ),
    "screening": frozenset(
        {
            "list_screeners",
            "list_recipes",
            "run_recipe",
            "propose_recipe",
            "screen_by_condition",
            "screen_by_pattern",
            "propose_screening",
            "get_screening_context",
            "explain_screening_run",
        }
    ),
    "backtest": frozenset(
        {
            "list_strategies",
            "get_backtest_result",
            "list_backtest_history",
            "list_strategy_signals",
        }
    ),
    "watchlist": frozenset(
        {
            "get_watchlist",
            "list_watchlist_positions",
            "add_to_watchlist",
            "remove_from_watchlist",
            "get_quote_context",
            "list_strategy_signals",
        }
    ),
    "data": frozenset(
        {
            "get_bars_summary",
            "get_bars_data",
            "read_skill_file",
            "run_python",
            "list_skill_files",
        }
    ),
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

market.fear_greed（恐贪指数 enrichment，三档）：
- skip：纯价格/自选 CRUD/回测数值/K 线条数等 factual 问答，勿调用恐贪工具
- consider：综合研判、个股值不值得看、选股环境、风险/节奏/大盘强弱相关时，由主对话自行判断是否调用与是否写入正文
- highlight：用户明显在问市场情绪、冷热、恐贪/贪婪/恐慌、赚钱效应、是否过热

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


def apply_fear_greed_tools(
    tools: list[dict[str, Any]],
    analysis: IntentAnalysis,
    all_tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """按 enrichment 三档加入或移除恐贪指数工具。"""
    available = {(tool.get("function") or {}).get("name", "") for tool in all_tools}
    if FEAR_GREED_TOOL not in available:
        return tools

    level = analysis.market.fear_greed
    if level == "skip":
        return [tool for tool in tools if (tool.get("function") or {}).get("name", "") != FEAR_GREED_TOOL]

    names = {(tool.get("function") or {}).get("name", "") for tool in tools}
    if FEAR_GREED_TOOL in names:
        return tools
    for tool in all_tools:
        if (tool.get("function") or {}).get("name", "") == FEAR_GREED_TOOL:
            return list(tools) + [tool]
    return tools


def _infer_market_enrichment(
    user_text: str,
    page: str,
    category: IntentCategory,
) -> MarketEnrichment:
    text = user_text.strip()

    highlight_keywords = (
        "恐贪",
        "贪婪",
        "恐慌",
        "市场情绪",
        "大盘情绪",
        "赚钱效应",
        "过热",
        "冰点",
        "市场冷热",
        "市场怎么样",
        "大盘怎么样",
    )
    skip_keywords = (
        "多少钱",
        "当前价",
        "涨了多少",
        "跌了多少",
        "加入自选",
        "移出自选",
        "删除自选",
        "清空自选",
        "下载",
        "导入",
    )
    if any(keyword in text for keyword in highlight_keywords):
        return MarketEnrichment(
            fear_greed="highlight",
            reasoning="用户关注全市场情绪或冷热",
        )
    if category == "watchlist":
        return MarketEnrichment(fear_greed="skip", reasoning="自选操作场景")
    if category == "backtest" and any(k in text for k in ("夏普", "回撤", "收益", "胜率", "回测结果")):
        return MarketEnrichment(fear_greed="skip", reasoning="回测数值解读")
    if category == "quote" and any(keyword in text for keyword in skip_keywords):
        return MarketEnrichment(fear_greed="skip", reasoning="纯行情 factual 查询")
    if page == "市场" and category in ("quote", "general"):
        return MarketEnrichment(fear_greed="consider", reasoning="市场页综合浏览")
    if category in ("general", "screening", "diagnosis"):
        return MarketEnrichment(fear_greed="consider", reasoning="综合研判场景")
    return MarketEnrichment(fear_greed="consider", reasoning="默认可由 AI 判断是否使用")


def _normalize_market_enrichment(
    analysis: IntentAnalysis,
    user_text: str,
    page: str,
) -> IntentAnalysis:
    inferred = _infer_market_enrichment(user_text, page, analysis.route.category)
    current = analysis.market.fear_greed

    if inferred.fear_greed == "highlight":
        return analysis.model_copy(update={"market": inferred})
    if inferred.fear_greed == "skip":
        return analysis.model_copy(update={"market": inferred})
    if current == "skip":
        return analysis
    if current == "highlight":
        return analysis
    return analysis.model_copy(
        update={
            "market": MarketEnrichment(
                fear_greed="consider",
                reasoning=inferred.reasoning or analysis.market.reasoning,
            )
        }
    )


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
            lines.append("- 意图不够明确，请先向用户追问，勿调用选股工具")
        elif s.confidence == "high" and s.preset and not s.scheme_name:
            lines.append(f"- 内置方案「{s.preset}」可直接调用 screen_by_condition（name={s.preset}, top_n={s.top_n}）")
        elif s.confidence in ("high", "medium"):
            lines.append("- 请调用 propose_screening，并传入上述 intent/preset/top_n 等参数")

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

    fg = analysis.market.fear_greed
    if fg == "skip":
        lines.append("【恐贪指数】本轮 skip：勿调用 get_ashare_fear_greed_index。")
    elif fg == "highlight":
        lines.append("【恐贪指数】本轮 highlight：建议调用 get_ashare_fear_greed_index，并在回答中结合工具数据简要说明市场环境（仍禁止具体买卖建议）。")
    else:
        lines.append("【恐贪指数】本轮 consider：可自行判断是否调用 get_ashare_fear_greed_index；与大盘节奏/风险/环境无关则勿调用；调用后也不必强行写入正文。")
    if analysis.market.reasoning:
        lines.append(f"- enrichment：{analysis.market.reasoning}")

    group = TOOL_GROUPS.get(route.category)
    if group:
        names = sorted(group | AGENT_TOOL_NAMES)
        lines.append(f"本轮可用工具子集：{', '.join(names)}")

    return "\n".join(lines)


def _keyword_fallback(user_text: str, page: str) -> IntentAnalysis | None:
    """API 不可用时的轻量规则兜底。"""
    text = user_text.strip()
    lower = text.lower()

    def _with_market(category: IntentCategory, **kwargs) -> IntentAnalysis:
        route = IntentRoute(category=category, confidence="medium", reasoning="关键词匹配")
        analysis = IntentAnalysis(route=route, **kwargs)
        return _normalize_market_enrichment(analysis, text, page)

    if any(k in text for k in ("选股", "筛选", "涨幅榜", "换手率", "涨最多")):
        return _with_market(
            "screening",
            screening=ScreeningIntent(intent=text, confidence="medium"),
        )
    if any(k in text for k in ("回测", "夏普", "最大回撤", "策略列表")):
        action = "list_history" if "历史" in text or "对比" in text else "query_result"
        if "有哪些策略" in text or "策略列表" in text:
            action = "list_strategies"
        return _with_market(
            "backtest",
            backtest=BacktestIntent(action=action, confidence="medium"),
        )
    if any(k in text for k in ("诊断", "研报", "评级", "券商")):
        return _with_market("diagnosis")
    if any(k in text for k in ("均线", "金叉", "死叉", "技术面", "形态")):
        return _with_market("technical")
    if page and page in PAGE_CATEGORY_HINT:
        cat = PAGE_CATEGORY_HINT[page]
        analysis = IntentAnalysis(
            route=IntentRoute(category=cat, confidence="low", reasoning=f"页面上下文 {page}"),
        )
        return _normalize_market_enrichment(analysis, text, page)
    if any(k in lower for k in ("多少钱", "涨了多少", "当前价")):
        return _with_market("quote")
    return None


def _structured_parse(config: LlmConfig, messages: list[dict[str, str]], model_type: type) -> Any:
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
        analysis = IntentAnalysis(route=IntentRoute(category="general", confidence="low"))
        return _normalize_market_enrichment(analysis, user_text, page)

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
        analysis = IntentAnalysis(route=IntentRoute(category="general", confidence="low"))
        return _normalize_market_enrichment(analysis, user_text, page)

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

    return _normalize_market_enrichment(analysis, user_text, page)


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
    tools = apply_fear_greed_tools(tools, analysis, all_tools)

    hint = build_routing_hint(analysis, page=page)
    return RouteContext(analysis=analysis, tools=tools, routing_hint=hint)
