"""行情上下文数据模型与组装。

供 QuoteService / ScreeningService 写入 context_store 前构造 ``AiContextData`` 与 ``QuickAction``。
"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.config import _CN_NAME_TO_EXCHANGE, exchange_to_cn
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.storage.app_db import load_watchlist_rows, position_contains
from vnpy_common.ai.protocol import AiContextData, QuickAction, StockCompletionItem


def format_quote_summary(quote: QuoteSnapshot | None) -> str:
    """将 QuoteSnapshot 格式化为单行行情摘要。"""
    if quote is None:
        return ""
    return (
        f"最新价 {quote.last_price:.2f}，涨跌 {quote.change_amount:+.2f}（{quote.change_pct:+.2f}%），"
        f"今开 {quote.open_price:.2f}，最高 {quote.high_price:.2f}，最低 {quote.low_price:.2f}，"
        f"昨收 {quote.prev_close:.2f}，换手率 {quote.turnover_rate:.2f}%"
    )


def build_quote_context(
    *,
    page: str,
    item: StockItem | None,
    quote: QuoteSnapshot | None = None,
    bar_count: int = 0,
    signal_extra: str = "",
) -> AiContextData:
    """组装看盘页 AI 上下文（含行情摘要与本地 K 线条数）。"""
    if item is None:
        return AiContextData(page=page)

    extra_parts: list[str] = []
    if bar_count > 0:
        extra_parts.append(f"本地日 K 条数：{bar_count}")
    else:
        extra_parts.append("本地日 K：暂无（需先下载）")
    signal_text = (signal_extra or "").strip()
    if signal_text:
        extra_parts.append(signal_text)

    return AiContextData(
        page=page,
        symbol=item.symbol,
        exchange=exchange_to_cn(item.exchange),
        name=item.name,
        quote_summary=format_quote_summary(quote),
        extra="\n".join(extra_parts),
    )


DEFAULT_FALLBACK_SYMBOL = "002230"
DEFAULT_FALLBACK_EXCHANGE_CN = "深交所"
DEFAULT_FALLBACK_NAME = "科大讯飞"
DEFAULT_FALLBACK_VT_SYMBOL = "002230.SZSE"


@dataclass(frozen=True)
class StockBinding:
    """快捷动作绑定的单票标识（symbol / vt_symbol / 展示名）。"""

    symbol: str
    exchange_cn: str
    name: str
    vt_symbol: str

    @property
    def title(self) -> str:
        if self.name:
            return f"{self.name}（{self.vt_symbol}）"
        return self.vt_symbol

    @property
    def tooltip(self) -> str:
        return f"绑定标的：{self.title}"


def resolve_assistant_stock_binding() -> StockBinding:
    """全屏助手：自选首只 → 否则写死默认标的。"""
    rows = load_watchlist_rows()
    if rows:
        symbol, exchange, name = rows[0]
        return StockBinding(
            symbol=symbol,
            exchange_cn=exchange_to_cn(exchange),
            name=name or symbol,
            vt_symbol=f"{symbol}.{exchange.value}",
        )
    return StockBinding(
        symbol=DEFAULT_FALLBACK_SYMBOL,
        exchange_cn=DEFAULT_FALLBACK_EXCHANGE_CN,
        name=DEFAULT_FALLBACK_NAME,
        vt_symbol=DEFAULT_FALLBACK_VT_SYMBOL,
    )


def resolve_vt_symbol(symbol: str, exchange_cn: str = "") -> str:
    """将代码 + 中文交易所名解析为工具可用的 vt_symbol（如 002230.SZSE）。"""
    if exchange_cn:
        exchange = _CN_NAME_TO_EXCHANGE.get(exchange_cn)
        if exchange is not None:
            return f"{symbol}.{exchange.value}"
    item = parse_stock_symbol(symbol)
    if item is not None:
        return item.vt_symbol
    return symbol


def resolve_selected_stock_binding(
    symbol: str,
    *,
    exchange_cn: str = "",
    name: str = "",
) -> StockBinding | None:
    """悬浮面板：绑定看盘页当前选中标的。"""
    if not symbol.strip():
        return None
    vt = resolve_vt_symbol(symbol, exchange_cn)
    return StockBinding(
        symbol=symbol.strip(),
        exchange_cn=exchange_cn,
        name=name or symbol.strip(),
        vt_symbol=vt,
    )


def build_diagnose_ai_prompt(vt_symbol: str, name: str = "") -> str:
    """生成跳转 AI 助手页的综合诊断预填文案。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return (
        f"请对 {title} 做综合诊断。"
        "请通过问小达获取行情、技术指标、财务、资金流、研报等数据，"
        "基于返回结果解读，不要编造未在结果中的指标或研报观点。"
    )


def build_technical_ai_prompt(vt_symbol: str, name: str = "") -> str:
    """生成技术形态分析预填文案。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return (
        f"请分析 {title} 的近期技术形态。"
        "涵盖均线排列、量比、区间涨跌等，基于实际数据做解读，不要编造。"
    )


def build_signals_ai_prompt(
    vt_symbol: str,
    name: str = "",
    *,
    class_name: str = "AshareDoubleMaStrategy",
    fast_window: int = 10,
    slow_window: int = 20,
) -> str:
    """生成双均线策略信号分析预填文案。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    fast = max(2, int(fast_window or 10))
    slow = max(fast + 1, int(slow_window or 20))
    return (
        f"请分析 {title} 的双均线（MA{fast}/MA{slow}）策略信号。"
        "解读金叉/死叉信号与当前均线状态，基于实际数据，不要编造。"
    )


def build_signal_panel_batch_ai_prompt(
    *,
    class_name: str = "AshareDoubleMaStrategy",
    fast_window: int = 10,
    slow_window: int = 20,
    symbol_count: int = 0,
) -> str:
    """信号区「AI 扫区」预填文案。"""
    fast = max(2, int(fast_window or 10))
    slow = max(fast + 1, int(slow_window or 20))
    count = max(0, int(symbol_count or 0))
    return (
        f"请扫描自选页策略信号区共 {count} 只监控标的的双均线（MA{fast}/MA{slow}）信号。"
        "汇总买入/卖出/观望分布，标出需关注的标的并说明理由；"
        "结合实时行情与信号快照解读，禁止给出具体买卖价或仓位建议。"
    )


def build_signal_panel_ai_prompt(
    vt_symbol: str,
    name: str = "",
    *,
    class_name: str = "AshareDoubleMaStrategy",
    fast_window: int = 10,
    slow_window: int = 20,
    context_extra: str = "",
) -> str:
    """信号区「AI 解读」预填文案：附带快照摘要 + 工具调用。"""
    base = build_signals_ai_prompt(
        vt_symbol,
        name,
        class_name=class_name,
        fast_window=fast_window,
        slow_window=slow_window,
    )
    snapshot_text = (context_extra or "").strip()
    if not snapshot_text:
        return (
            f"{base}"
            "结合当前行情与信号区展示字段（参考价、距买价%）做研究解读，禁止给出具体买卖价或仓位建议。"
        )
    return (
        f"已知信号区快照（规则计算，非买卖建议）：\n{snapshot_text}\n\n"
        f"{base}"
        "结合上述快照与工具返回核对解读；盘中提示仅供参考，禁止给出具体买卖价或仓位建议。"
    )


def build_positions_ai_prompt(
    vt_symbol: str,
    name: str = "",
    *,
    class_name: str = "AshareDoubleMaStrategy",
    fast_window: int = 10,
    slow_window: int = 20,
    cost_price: float | None = None,
    volume: int | None = None,
    unrealized_pnl_pct: float | None = None,
    t1_locked: bool | None = None,
) -> str:
    """生成持仓策略分析预填文案。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    fast = max(2, int(fast_window or 10))
    slow = max(fast + 1, int(slow_window or 20))
    context_parts: list[str] = []
    if cost_price is not None:
        context_parts.append(f"记账成本价 {cost_price:.2f} 元")
    if volume is not None:
        context_parts.append(f"持仓量 {volume} 股")
    if unrealized_pnl_pct is not None:
        context_parts.append(f"浮盈 {unrealized_pnl_pct:+.2f}%")
    if t1_locked is not None:
        context_parts.append("T+1 锁定" if t1_locked else "可卖（非 T+1 锁定）")
    context_line = f"已知持仓：{'；'.join(context_parts)}。" if context_parts else ""
    return (
        f"请从持仓策略角度分析 {title} 的退出时机与风险。"
        f"{context_line}"
        f"请先核对记账持仓，再分析双均线（MA{fast}/MA{slow}）退出信号。"
        "结合持仓成本、浮盈与策略信号做研究解读，禁止给出具体买卖价或仓位建议。"
    )


def build_historical_ai_prompt(
    vt_symbol: str,
    name: str = "",
    *,
    lookback: int = 20,
) -> str:
    """生成历史走势统计预填文案（禁止预测）。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return (
        f"请分析 {title} 的近 {int(lookback)} 日走势。"
        "优先使用本地日 K 统计，本地不足时自动补充问小达数据；"
        "基于涨跌幅、波动、连涨连跌等历史统计数据做描述，禁止预测未来走势。"
        "请按以下结构组织回答：\n"
        "1. **一句话总结**：趋势标签与区间涨跌幅\n"
        "2. **价格区间**：起止收盘价、区间最高/最低与振幅\n"
        "3. **节奏特征**：当前连涨/连跌、最长连涨/连跌天数、形态标签\n"
        "4. **量价配合**：均线排列、近 5 日量比\n"
        "5. **免责说明**：注明数据局限"
    )


def build_trend_ai_prompt(vt_symbol: str, name: str = "") -> str:
    """近 20 日走势快捷入口（``build_historical_ai_prompt`` 默认 lookback）。"""
    return build_historical_ai_prompt(vt_symbol, name, lookback=20)


_TREND_SCENARIO_OUTPUT = (
    "按乐观/基准/悲观三情景输出（概率表述 + 触发/失效条件），"
    "结合上下文中的信号快照交叉核对，"
    "必要时通过问小达补充 MACD/KDJ/RSI 与主力资金，"
    "方向类问题可酌情参考大盘情绪背景；"
    "禁止确定性预测与具体买卖价位。"
)


def build_trend_scenario_ai_prompt(
    vt_symbol: str,
    name: str = "",
    *,
    focus: str = "general",
    horizon_days: int = 5,
    class_name: str = "AshareDoubleMaStrategy",
    fast_window: int = 10,
    slow_window: int = 20,
) -> str:
    """走势预测快捷入口（本地情景摘要 + 可选问小达补充）。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    horizon = max(1, min(int(horizon_days or 5), 20))
    fast = max(2, int(fast_window or 10))
    slow = max(fast + 1, int(slow_window or 20))
    base = (
        f"请对 {title} 做走势情景分析（非确定性预测，展望 {horizon} 日）。"
        f"基于本地均线（MA{fast}/MA{slow}）、结构锚点与统计参考带组织分析。"
    )
    focus_lines = {
        "price": "重点解读参考波动区间与结构锚点，给出可能的价位情景。",
        "support": "重点列出支撑/阻力锚点及距买/卖参考价的偏离，并用问小达交叉验证。",
        "5d": f"重点结合短期动能与方向提示，描述 {horizon} 日可能情景。",
        "direction": "重点解读多空方向提示、均线排列与规则信号，给出倾向与不确定性说明。",
        "general": "综合技术面、动能、结构锚点与方向提示组织三情景。",
    }
    detail = focus_lines.get(focus, focus_lines["general"])
    return f"{base}{detail}{_TREND_SCENARIO_OUTPUT}"


def resolve_signal_prompt_params() -> tuple[str, int, int]:
    """读取自选页信号区策略参数（与信号面板设置一致）。"""
    try:
        from vnpy_ashare.ui.quotes.watchlist_signals.settings import load_watchlist_signal_config

        cfg = load_watchlist_signal_config()
        return cfg.class_name, cfg.fast_window, cfg.slow_window
    except Exception:
        return "AshareDoubleMaStrategy", 10, 20


def build_stock_completion_items(
    symbol: str,
    *,
    exchange_cn: str = "",
    name: str = "",
) -> list[StockCompletionItem]:
    """输入框联想项：诊断 / 技术面 / 双均线 / 近期走势。"""
    vt = resolve_vt_symbol(symbol, exchange_cn)
    display = name or symbol
    class_name, fast_window, slow_window = resolve_signal_prompt_params()
    return [
        StockCompletionItem(
            f"诊断 {display}({symbol})",
            build_diagnose_ai_prompt(vt, name),
        ),
        StockCompletionItem(
            f"{display}({symbol}) 技术面",
            build_technical_ai_prompt(vt, name),
        ),
        StockCompletionItem(
            f"{display}({symbol}) 双均线",
            build_signals_ai_prompt(vt, name),
        ),
        StockCompletionItem(
            f"{display}({symbol}) 近期走势",
            build_trend_ai_prompt(vt, name),
        ),
        StockCompletionItem(
            f"{display}({symbol}) 5日情景",
            build_trend_scenario_ai_prompt(
                vt,
                name,
                focus="5d",
                class_name=class_name,
                fast_window=fast_window,
                slow_window=slow_window,
            ),
        ),
        StockCompletionItem(
            f"{display}({symbol}) 支撑压力",
            build_trend_scenario_ai_prompt(
                vt,
                name,
                focus="support",
                class_name=class_name,
                fast_window=fast_window,
                slow_window=slow_window,
            ),
        ),
    ]


def _wenda_prefix(binding: StockBinding) -> str:
    return f"针对 {binding.title}，"


def build_diagnose_menu(binding: StockBinding) -> QuickAction:
    """综合诊断二级菜单（全量 / 财务 / 研报 / 资金流）。"""
    prefix = _wenda_prefix(binding)
    vt = binding.vt_symbol
    name = binding.name
    return QuickAction(
        id="diagnose",
        label="综合诊断",
        tooltip=binding.tooltip,
        children=[
            QuickAction(
                id="diagnose_full",
                label="综合诊断",
                prompt=build_diagnose_ai_prompt(vt, name),
            ),
            QuickAction(
                id="diagnose_finance",
                label="财务估值",
                prompt=(
                    f"{prefix}请通过问小达查询市盈率、ROE 等财务估值指标，"
                    "必要时结合综合诊断数据，基于返回结果解读，禁止编造。"
                ),
            ),
            QuickAction(
                id="diagnose_report",
                label="研报评级",
                prompt=(f"{prefix}请通过问小达查询最新研报与评级，引用须注明来源与日期，禁止编造。"),
            ),
            QuickAction(
                id="diagnose_flow",
                label="资金流向",
                prompt=(f"{prefix}请通过问小达查询主力资金流向，基于返回数据描述资金面，禁止编造。"),
            ),
        ],
    )


def build_technical_menu(binding: StockBinding) -> QuickAction:
    """技术形态二级菜单（均线量比 / 指标 / 双均线）。"""
    prefix = _wenda_prefix(binding)
    vt = binding.vt_symbol
    name = binding.name
    return QuickAction(
        id="technical",
        label="技术形态",
        tooltip=binding.tooltip,
        children=[
            QuickAction(
                id="technical_ma",
                label="均线量比",
                prompt=build_technical_ai_prompt(vt, name),
            ),
            QuickAction(
                id="technical_indicator",
                label="MACD/KDJ/RSI",
                prompt=(f"{prefix}请通过问小达查询 MACD、KDJ、RSI 等技术指标，基于返回数据做技术解读，非买卖建议。"),
            ),
            QuickAction(
                id="technical_signals",
                label="双均线信号",
                prompt=build_signals_ai_prompt(vt, name),
            ),
        ],
    )


def build_recent_trend_menu(binding: StockBinding) -> QuickAction:
    """近期走势二级菜单（5 / 20 / 60 日）。"""
    vt = binding.vt_symbol
    name = binding.name
    return QuickAction(
        id="recent_trend",
        label="近期走势",
        tooltip=binding.tooltip,
        children=[
            QuickAction(
                id="recent_5d",
                label="近5日",
                prompt=build_historical_ai_prompt(vt, name, lookback=5),
            ),
            QuickAction(
                id="recent_20d",
                label="近20日",
                prompt=build_historical_ai_prompt(vt, name, lookback=20),
            ),
            QuickAction(
                id="recent_60d",
                label="近60日",
                prompt=build_historical_ai_prompt(vt, name, lookback=60),
            ),
        ],
    )


def build_trend_forecast_menu(
    binding: StockBinding,
    *,
    class_name: str = "AshareDoubleMaStrategy",
    fast_window: int = 10,
    slow_window: int = 20,
) -> QuickAction:
    """走势预测二级菜单（本地情景摘要 + MCP 补充，非确定性买卖建议）。"""
    vt = binding.vt_symbol
    name = binding.name
    prompt_kwargs = {
        "class_name": class_name,
        "fast_window": fast_window,
        "slow_window": slow_window,
    }
    return QuickAction(
        id="trend_forecast",
        label="走势预测",
        tooltip=f"{binding.tooltip} · 本地结构 + 问小达补充 · 情景分析",
        children=[
            QuickAction(
                id="trend_price",
                label="股价预测",
                auto_send=True,
                prompt=build_trend_scenario_ai_prompt(vt, name, focus="price", **prompt_kwargs),
            ),
            QuickAction(
                id="trend_support",
                label="支撑压力位",
                auto_send=True,
                prompt=build_trend_scenario_ai_prompt(vt, name, focus="support", **prompt_kwargs),
            ),
            QuickAction(
                id="trend_5d",
                label="5日走势预测",
                auto_send=True,
                prompt=build_trend_scenario_ai_prompt(
                    vt,
                    name,
                    focus="5d",
                    horizon_days=5,
                    **prompt_kwargs,
                ),
            ),
            QuickAction(
                id="trend_direction",
                label="方向预测",
                auto_send=True,
                prompt=build_trend_scenario_ai_prompt(vt, name, focus="direction", **prompt_kwargs),
            ),
        ],
    )


def build_bound_stock_menus(binding: StockBinding) -> list[QuickAction]:
    """四组快捷菜单：综合诊断 / 技术形态 / 走势预测 / 近期走势。"""
    class_name, fast_window, slow_window = resolve_signal_prompt_params()
    return [
        build_diagnose_menu(binding),
        build_technical_menu(binding),
        build_trend_forecast_menu(
            binding,
            class_name=class_name,
            fast_window=fast_window,
            slow_window=slow_window,
        ),
        build_recent_trend_menu(binding),
    ]


def build_sector_overview_prompt(vt_symbol: str, name: str = "") -> str:
    """市场页：所属板块/概念行业联动分析预填文案。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return (
        f"请分析 {title} 所属板块/概念行业的近期表现与联动逻辑。"
        "可通过问小达查询板块关联、成分股联动与主力资金流向，"
        "基于返回数据解读，禁止编造未在结果中的板块数据。"
    )


def build_bar_health_prompt(vt_symbol: str, name: str = "", extra: str = "") -> str:
    """本地页：日 K 覆盖/过期/断层检查预填文案。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    context = f"当前上下文：{extra.strip()}\n" if extra.strip() else ""
    return (
        f"{context}请检查 {title} 的本地日 K 覆盖是否完整、是否过期或存在断层。"
        "获取起止日期与条数，结合上下文说明数据健康状态，并给出补全或重下建议（不要直接执行下载）。"
    )


def build_add_watchlist_prompt(vt_symbol: str, name: str = "") -> str:
    """非自选页：加入自选池预填文案。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return f"请将 {title} 加入自选池，并告知是否成功。"


def build_reference_peer_prompt(vt_symbol: str, name: str = "", *, top_n: int = 20) -> str:
    """标杆对标（找同类）预填文案：同业 + 估值接近 + 近 5 日动量。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    count = max(1, min(int(top_n or 20), 100))
    return (
        f"请以 {title} 为标杆，在全市场找同类标的（同业 40% + 估值接近 35% + 近 5 日动量 25%）。"
        f"返回 Top {count}，用 Markdown 表格展示，列含代码、名称、相似分、入选原因、PE TTM、5 日涨跌%；"
        f"简要解读 Top {min(5, count)} 与标杆的差异及可研究点，禁止编造未在结果中的数据。"
    )


def is_symbol_in_positions(vt_symbol: str) -> bool:
    """判断标的是否已登记持仓记账。"""
    from vnpy_ashare.ai.context.symbol import parse_stock_symbol

    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return False
    return position_contains(item.symbol, item.exchange)


def is_symbol_in_watchlist(symbol: str, exchange_cn: str = "") -> bool:
    """判断标的是否已在自选池。"""
    if not symbol.strip():
        return False
    exchange = _CN_NAME_TO_EXCHANGE.get(exchange_cn) if exchange_cn else None
    for row_symbol, row_exchange, _ in load_watchlist_rows():
        if row_symbol != symbol.strip():
            continue
        if exchange is None or row_exchange == exchange:
            return True
    return False


def build_floating_page_extras(
    page: str,
    binding: StockBinding,
    *,
    extra: str = "",
) -> list[QuickAction]:
    """按看盘页类型追加扁平快捷动作（板块概览 / 数据健康 / 加入自选）。"""
    extras: list[QuickAction] = []
    vt = binding.vt_symbol
    name = binding.name
    if page in ("自选", "市场", "雷达"):
        extras.append(
            QuickAction(
                id="reference_peer",
                label="找同类",
                prompt=build_reference_peer_prompt(vt, name),
            )
        )
    if page == "市场" or page == "雷达":
        extras.append(
            QuickAction(
                id="sector_overview",
                label="板块概览",
                prompt=build_sector_overview_prompt(vt, name),
            )
        )
    elif page == "本地":
        extras.append(
            QuickAction(
                id="bar_health",
                label="数据健康",
                prompt=build_bar_health_prompt(vt, name, extra),
            )
        )
    if page == "自选" and is_symbol_in_positions(vt):
        extras.append(
            QuickAction(
                id="position_strategy",
                label="持仓策略",
                prompt=build_positions_ai_prompt(vt, name),
            )
        )
    if page != "自选" and not is_symbol_in_watchlist(binding.symbol, binding.exchange_cn):
        extras.append(
            QuickAction(
                id="add_watchlist",
                label="加入自选",
                prompt=build_add_watchlist_prompt(vt, name),
            )
        )
    return extras


def _pattern_screen_prompt(pattern: str, *, detail: str = "") -> str:
    detail_text = f"{detail} " if detail else ""
    return (
        f"请执行形态选股「{pattern}」。{detail_text}"
        "优先通过问小达全市场扫描，不可用时降级本地日 K。"
        "完成后用 Markdown 表格展示 Top 20（含形态得分、形态说明、数据来源），"
        "并说明扫描范围。"
    )


def _recipe_screen_prompt(
    recipe_id: str,
    label: str,
    *,
    detail: str = "",
    top_n: int = 20,
) -> str:
    detail_text = f"{detail} " if detail else ""
    timing = {"intraday_multi": "盘中", "post_close_multi": "盘后"}.get(recipe_id, "")
    timing_text = f"{timing}" if timing else ""
    return (
        f"请执行{timing_text}多因子选股「{label}」。{detail_text}"
        f"直接在全市场筛选 Top {top_n}，勿等待用户确认。"
        "完成后用 Markdown 表格展示（含综合得分、入选原因、各维度得分），"
        "并说明扫描范围、数据来源与配方维度含义。"
    )


def _preset_screen_prompt(
    preset_name: str,
    label: str,
    *,
    detail: str = "",
    top_n: int = 20,
) -> str:
    detail_text = f"{detail} " if detail else ""
    return (
        f"请按「{label}」方案（{preset_name}）在全市场选股。{detail_text}"
        f"直接筛选 Top {top_n}，勿等待用户确认。"
        "完成后用 Markdown 表格展示 Top 结果，并说明扫描范围与数据来源。"
    )


def _screening_prompt(intent: str, *, detail: str = "") -> str:
    extra = f" {detail}" if detail else ""
    return (
        f"请按「{intent}」在 A 股中选股。{extra}"
        "可先了解可用方案与多因子配方；"
        "盘中/盘后多因子意图明确时直接执行对应配方；"
        "内置条件明确时按 preset 筛选；"
        "形态选股（老鸭头/均线多头/W底/主题投资）优先走形态扫描；"
        "已保存方案或条件较复杂时可先梳理条件再执行；"
        "自定义区间需明确涨幅/换手阈值。"
        "结果用 Markdown 表格展示，默认 Top 20，排除 ST，注明数据来源。"
    )


def build_pattern_screen_menu() -> QuickAction:
    """全市场形态选股二级菜单（老鸭头 / 均线多头 / W底 / 热点活跃）。"""
    return QuickAction(
        id="pattern_screen",
        label="形态选股",
        tooltip="优先通达信问小达 MCP 全市场扫描，MCP 不可用时降级本地日 K",
        children=[
            QuickAction(
                id="pattern_old_duck",
                label="老鸭头形态",
                auto_send=True,
                prompt=_pattern_screen_prompt(
                    "老鸭头形态",
                    detail="关注放量突破、短期均线回踩后再次上攻。",
                ),
            ),
            QuickAction(
                id="pattern_ma_bull",
                label="均线多头",
                auto_send=True,
                prompt=_pattern_screen_prompt(
                    "均线多头排列",
                    detail="优先 MA5>MA10>MA20>MA60，现价站上关键均线。",
                ),
            ),
            QuickAction(
                id="pattern_w_bottom",
                label="W底形态",
                auto_send=True,
                prompt=_pattern_screen_prompt(
                    "W底形态",
                    detail="关注双底结构、第二次探底缩量、突破颈线放量。",
                ),
            ),
            QuickAction(
                id="pattern_theme",
                label="热点活跃",
                auto_send=True,
                tooltip="全市场行情筛选，非 K 线形态；需行情采集",
                prompt=_pattern_screen_prompt(
                    "主题投资",
                    detail="基于全市场行情的高换手+涨幅活跃筛选。",
                ),
            ),
        ],
    )


def build_condition_screen_menu() -> QuickAction:
    """全市场条件选股二级菜单（风格标签 → 固定 recipe / preset）。"""
    return QuickAction(
        id="condition_screen",
        label="条件选股",
        tooltip="A 股全市场条件选股（每项绑定固定配方或内置方案）",
        children=[
            QuickAction(
                id="cond_short_hot",
                label="短线游资",
                auto_send=True,
                tooltip="盘中多因子：动量 + 量比 + 板块 + 换手 + 放量",
                prompt=_recipe_screen_prompt(
                    "intraday_multi",
                    "短线游资",
                    detail="关注题材活跃度、高换手与盘中异动，适合短线跟踪研究。",
                ),
            ),
            QuickAction(
                id="cond_mid_swing",
                label="中线波段",
                auto_send=True,
                tooltip="盘后多因子：资金 + 估值 + 动量",
                prompt=_recipe_screen_prompt(
                    "post_close_multi",
                    "中线波段",
                    detail="持有数周至数月，兼顾趋势、资金与估值，关注波段空间。",
                ),
            ),
            QuickAction(
                id="cond_long_value",
                label="长线价投",
                auto_send=True,
                tooltip="内置方案：低 PE（Tushare daily_basic）",
                prompt=_preset_screen_prompt(
                    "低 PE",
                    "长线价投",
                    detail="低估值筛选，适合长期持有研究（需 TUSHARE_TOKEN）。",
                ),
            ),
            QuickAction(
                id="cond_growth",
                label="成长赛道",
                auto_send=True,
                tooltip="内置方案：主力净流入（Tushare moneyflow）",
                prompt=_preset_screen_prompt(
                    "主力净流入",
                    "成长赛道",
                    detail="资金关注度高的标的，可结合赛道逻辑进一步解读。",
                ),
            ),
            QuickAction(
                id="cond_cyclical",
                label="周期资源",
                auto_send=True,
                tooltip="内置方案：成交量放大（Redis 行情）",
                prompt=_preset_screen_prompt(
                    "成交量放大",
                    "周期资源",
                    detail="量能异动筛选，可结合商品/资源板块景气度解读。",
                ),
            ),
        ],
    )


def build_reference_peer_menu(binding: StockBinding) -> QuickAction:
    """标杆对标（找同类）二级菜单，绑定当前标的。"""
    vt = binding.vt_symbol
    name = binding.name
    return QuickAction(
        id="reference_peer",
        label="找同类",
        tooltip=f"以 {binding.title} 为标杆：同业 + 估值 + 动量",
        children=[
            QuickAction(
                id="ref_peer_10",
                label="Top 10",
                prompt=build_reference_peer_prompt(vt, name, top_n=10),
            ),
            QuickAction(
                id="ref_peer_20",
                label="Top 20",
                prompt=build_reference_peer_prompt(vt, name, top_n=20),
            ),
            QuickAction(
                id="ref_peer_30",
                label="Top 30",
                prompt=build_reference_peer_prompt(vt, name, top_n=30),
            ),
        ],
    )


def build_assistant_screening_menus() -> list[QuickAction]:
    """全屏助手专用：形态/条件选股（全市场，不绑定单票）。"""
    return [
        build_pattern_screen_menu(),
        build_condition_screen_menu(),
    ]


def build_assistant_quick_actions() -> list[QuickAction]:
    """全屏 AI 助手：单票分析 + 标杆对标 + 全市场选股。"""
    binding = resolve_assistant_stock_binding()
    return [
        *build_bound_stock_menus(binding),
        build_reference_peer_menu(binding),
        *build_assistant_screening_menus(),
    ]


def build_floating_stock_quick_actions(
    symbol: str,
    *,
    exchange_cn: str = "",
    name: str = "",
    page: str = "",
    extra: str = "",
) -> list[QuickAction]:
    """悬浮面板：绑定看盘页选中标的。"""
    binding = resolve_selected_stock_binding(symbol, exchange_cn=exchange_cn, name=name)
    if binding is None:
        return []
    actions = build_bound_stock_menus(binding)
    actions.extend(build_floating_page_extras(page, binding, extra=extra))
    return actions


def build_stock_quick_actions(symbol: str, *, exchange_cn: str = "", name: str = "") -> list[QuickAction]:
    """看盘页快捷指令（悬浮/上下文同步）。"""
    return build_floating_stock_quick_actions(symbol, exchange_cn=exchange_cn, name=name)
