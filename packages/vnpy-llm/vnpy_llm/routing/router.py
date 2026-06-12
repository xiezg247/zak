"""两阶段意图路由：分类 → 工具子集 + 结构化提示。"""

from __future__ import annotations

import json
import re
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
            "list_watchlist_signal_panel",
            "historical_pattern_summary",
            "trend_scenario_summary",
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
            "propose_screening",
            "screen_by_pattern",
            "screen_reference_peer",
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
            "list_watchlist_signal_panel",
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
screening 补充：短线游资/题材活跃 → recipe_id=intraday_multi；中线波段 → recipe_id=post_close_multi；
长线价投 → preset=低 PE；成长赛道 → preset=主力净流入；周期资源 → preset=成交量放大。
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
    # run_python 仅 data 域（tushare/tickflow）；选股/诊断等禁止 run_python 以免误调 Agent Skill 脚本
    if category == "data":
        allowed.update(AGENT_TOOL_NAMES)

    mcp_names = mcp_tool_names or frozenset()
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


_TREND_SCENARIO_KEYWORDS = (
    "走势情景",
    "情景分析",
    "走势预测",
    "支撑压力",
    "方向预测",
    "5日走势",
    "5日情景",
    "股价预测",
)


def _is_trend_scenario_request(user_text: str) -> bool:
    text = user_text.strip()
    return any(keyword in text for keyword in _TREND_SCENARIO_KEYWORDS)


def _extract_trend_scenario_params(user_text: str) -> dict[str, int | str]:
    params: dict[str, int | str] = {}
    symbol_match = re.search(r"（(\d{6}\.[A-Z]+)）", user_text)
    if symbol_match:
        params["symbol"] = symbol_match.group(1)
    horizon_match = re.search(r"展望\s*(\d+)\s*日", user_text)
    if horizon_match:
        params["horizon_days"] = int(horizon_match.group(1))
    ma_match = re.search(r"MA(\d+)/MA(\d+)", user_text)
    if ma_match:
        params["fast_window"] = int(ma_match.group(1))
        params["slow_window"] = int(ma_match.group(2))
    return params


def _trend_scenario_routing_lines(user_text: str) -> list[str]:
    if not _is_trend_scenario_request(user_text):
        return []
    lines = [
        "【走势情景路由】",
        "- 优先且通常仅需调用一次 trend_scenario_summary，拿到结果后直接输出三情景",
        "- 勿再调用 technical_snapshot / historical_pattern_summary / list_strategy_signals / get_bars_*",
    ]
    params = _extract_trend_scenario_params(user_text)
    if params.get("symbol"):
        args: list[str] = [f'symbol="{params["symbol"]}"']
        if params.get("horizon_days") is not None:
            args.append(f"horizon_days={params['horizon_days']}")
        if params.get("fast_window") is not None:
            args.append(f"fast_window={params['fast_window']}")
        if params.get("slow_window") is not None:
            args.append(f"slow_window={params['slow_window']}")
        lines.append(f"- 建议调用：trend_scenario_summary({', '.join(args)})")
    return lines


def build_routing_hint(analysis: IntentAnalysis, *, page: str = "", user_text: str = "") -> str:
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
        if s.recipe_id:
            lines.append(f"- recipe_id: {s.recipe_id}")
        if s.trigger_kind:
            lines.append(f"- trigger_kind: {s.trigger_kind}")
        lines.append(f"- top_n: {s.top_n}")
        if s.scheme_name:
            lines.append(f"- scheme_name: {s.scheme_name}")
        lines.append(f"- confidence: {s.confidence}")
        lines.extend(_screening_tool_routing_lines(s))

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

    trend_scenario = _is_trend_scenario_request(user_text)
    lines.extend(_trend_scenario_routing_lines(user_text))
    if route.category == "screening":
        top_n = analysis.screening.top_n if analysis.screening else 20
        lines.extend(_pattern_screen_routing_lines(user_text, top_n=top_n))

    fg = analysis.market.fear_greed
    if trend_scenario:
        lines.append("【恐贪指数】本轮 skip：走势情景分析勿调用 get_ashare_fear_greed_index。")
    elif fg == "skip":
        lines.append("【恐贪指数】本轮 skip：勿调用 get_ashare_fear_greed_index。")
    elif fg == "highlight":
        lines.append("【恐贪指数】本轮 highlight：建议调用 get_ashare_fear_greed_index，并在回答中结合工具数据简要说明市场环境（仍禁止具体买卖建议）。")
    else:
        lines.append("【恐贪指数】本轮 consider：可自行判断是否调用 get_ashare_fear_greed_index；与大盘节奏/风险/环境无关则勿调用；调用后也不必强行写入正文。")
    if analysis.market.reasoning:
        lines.append(f"- enrichment：{analysis.market.reasoning}")

    group = TOOL_GROUPS.get(route.category)
    if group:
        names = sorted(group)
        if route.category == "data":
            names = sorted(group | AGENT_TOOL_NAMES)
        lines.append(f"本轮可用工具子集：{', '.join(names)}")

    return "\n".join(lines)


def _screening_tool_routing_lines(screening: ScreeningIntent) -> list[str]:
    """选股工具路由提示：LLM 自主解析并直接执行，无弹窗确认。"""
    s = screening
    if s.clarification_needed or s.confidence == "low":
        return ["- 意图不够明确，请先向用户追问，勿调用选股工具"]

    if s.scheme_name:
        return [
            f"- 已保存方案调用 propose_screening（scheme_name={s.scheme_name}, top_n={s.top_n}），解析后自动执行",
        ]

    has_custom_threshold = any(value is not None for value in (s.min_change_pct, s.max_change_pct, s.min_turnover))

    if s.recipe_id and s.confidence == "high":
        return [f"- 配方「{s.recipe_id}」直接 run_recipe（recipe_id={s.recipe_id}, top_n={s.top_n}）"]

    if s.preset and s.confidence == "high":
        if has_custom_threshold:
            return [
                f"- 自定义区间调用 propose_screening（preset={s.preset}, top_n={s.top_n}），解析后自动执行",
            ]
        return [f"- 内置方案「{s.preset}」直接 screen_by_condition（name={s.preset}, top_n={s.top_n}）"]

    if s.confidence in ("high", "medium"):
        if s.recipe_id:
            return [f"- 可直接 run_recipe（recipe_id={s.recipe_id}, top_n={s.top_n}）"]
        if s.preset:
            if has_custom_threshold:
                return [
                    f"- 调用 propose_screening（preset={s.preset}, top_n={s.top_n}），解析后自动执行",
                ]
            return [f"- 可直接 screen_by_condition（name={s.preset}, top_n={s.top_n}）"]
        return [
            "- 复杂/自定义多因子调用 propose_recipe；已保存方案或需解析的条件调用 propose_screening（均自动执行）",
            "- recipe_id / preset 明确时仍可直接 run_recipe / screen_by_condition",
        ]

    return ["- 请先 list_screeners / list_recipes 了解可用方案"]


_PATTERN_ALIASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("老鸭头",), "老鸭头形态"),
    (("均线多头", "多头排列", "bullish_alignment"), "均线多头排列"),
    (("w底", "双底", "w_bottom"), "W底形态"),
    (("热点活跃", "高换手", "主题投资"), "主题投资"),
)


def _resolve_pattern_screen_name(text: str) -> str | None:
    lower = text.lower()
    for keywords, pattern in _PATTERN_ALIASES:
        if any(k in text or k in lower for k in keywords):
            return pattern
    if "形态" in text and "均线" in text:
        return "均线多头排列"
    return None


def _pattern_screen_routing_lines(user_text: str, *, top_n: int = 20) -> list[str]:
    pattern = _resolve_pattern_screen_name(user_text)
    if not pattern:
        return []
    return [
        "【形态选股路由】",
        f'- 直接调用 screen_by_pattern(pattern="{pattern}", top_n={top_n})',
        '- 禁止 run_python(skill="tdx-stock-picker")：该 Skill 仅 Markdown，无 tdx_stock_picker 模块',
    ]


def _screening_intent_from_keywords(text: str) -> ScreeningIntent:
    """快捷菜单 / 口语关键词 → 结构化选股意图（关键词兜底用）。"""
    if any(k in text for k in ("短线游资", "游资", "题材活跃", "连板", "涨停")):
        return ScreeningIntent(
            intent=text,
            recipe_id="intraday_multi",
            trigger_kind="intraday",
            confidence="high",
        )
    if any(k in text for k in ("中线波段", "波段")):
        return ScreeningIntent(
            intent=text,
            recipe_id="post_close_multi",
            trigger_kind="post_close",
            confidence="high",
        )
    if any(k in text for k in ("长线价投", "价投", "价值投资")):
        return ScreeningIntent(intent=text, preset="低 PE", confidence="high")
    if any(k in text for k in ("成长赛道", "成长")):
        return ScreeningIntent(intent=text, preset="主力净流入", confidence="high")
    if any(k in text for k in ("周期资源", "周期")):
        return ScreeningIntent(intent=text, preset="成交量放大", confidence="high")
    if any(k in text for k in ("涨幅榜", "涨最多", "今天涨")):
        return ScreeningIntent(intent=text, preset="涨幅榜", confidence="high")
    if any(k in text for k in ("老鸭头", "均线多头", "多头排列", "w底", "双底", "形态选股")):
        return ScreeningIntent(intent=text, confidence="high")
    if "换手" in text:
        return ScreeningIntent(intent=text, preset="换手率排行", confidence="high")
    return ScreeningIntent(intent=text, confidence="medium")


def _keyword_fallback(user_text: str, page: str) -> IntentAnalysis | None:
    """API 不可用时的轻量规则兜底。"""
    text = user_text.strip()
    lower = text.lower()

    def _with_market(category: IntentCategory, **kwargs) -> IntentAnalysis:
        route = IntentRoute(category=category, confidence="medium", reasoning="关键词匹配")
        analysis = IntentAnalysis(route=route, **kwargs)
        return _normalize_market_enrichment(analysis, text, page)

    _SCREENING_KEYWORDS = (
        "选股",
        "筛选",
        "涨幅榜",
        "换手率",
        "涨最多",
        "短线游资",
        "游资",
        "中线波段",
        "波段",
        "长线价投",
        "价投",
        "成长赛道",
        "周期资源",
        "低 pe",
        "低pe",
        "多因子",
    )
    if any(k in text for k in _SCREENING_KEYWORDS) or any(k in lower for k in ("低pe",)):
        screening = _screening_intent_from_keywords(text)
        return _with_market("screening", screening=screening)
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
    if _is_trend_scenario_request(text) or any(k in text for k in ("均线", "金叉", "死叉", "技术面", "形态")):
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


def _strip_screening_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """选股意图不明确时剔除全部 screening 工具，迫使 LLM 先追问。"""
    blocked = TOOL_GROUPS["screening"]
    return [tool for tool in tools if (tool.get("function") or {}).get("name", "") not in blocked]


def _resolve_route_tools(
    analysis: IntentAnalysis,
    all_tools: list[dict[str, Any]],
    user_text: str,
    *,
    mcp_tool_names: frozenset[str] | set[str] | None,
) -> list[dict[str, Any]]:
    """按意图收窄本轮可用工具（runner 再与 Agent 域取交集）。

    阶段：类别子集 → 选股澄清 → 恐贪 enrichment → 走势情景剔除恐贪
    """
    category = analysis.route.category
    if analysis.route.confidence == "low" and category != "general":
        tools: list[dict[str, Any]] = []
    else:
        tools = filter_tools_by_route(all_tools, category, mcp_tool_names=mcp_tool_names)

    screening = analysis.screening
    if (
        category == "screening"
        and screening is not None
        and (screening.clarification_needed or screening.confidence == "low")
    ):
        tools = _strip_screening_tools(tools)

    tools = apply_fear_greed_tools(tools, analysis, all_tools)
    if _is_trend_scenario_request(user_text):
        tools = [tool for tool in tools if (tool.get("function") or {}).get("name", "") != FEAR_GREED_TOOL]
    return tools


def build_route_context(
    config: LlmConfig,
    user_text: str,
    all_tools: list[dict[str, Any]],
    *,
    page: str = "",
    mcp_tool_names: frozenset[str] | set[str] | None = None,
) -> RouteContext:
    """完整路由：分析意图 → 过滤工具 → 生成 routing_hint。"""
    analysis = analyze_user_intent(config, user_text, page=page)
    tools = _resolve_route_tools(
        analysis,
        all_tools,
        user_text,
        mcp_tool_names=mcp_tool_names,
    )
    hint = build_routing_hint(analysis, page=page, user_text=user_text)
    return RouteContext(analysis=analysis, tools=tools, routing_hint=hint)
