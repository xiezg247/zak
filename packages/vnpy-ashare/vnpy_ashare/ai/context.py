"""行情上下文数据模型与组装。

供 QuoteService / ScreeningService 写入 context_store 前构造 ``AiContextData`` 与 ``QuickAction``。
"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.ai.symbol import parse_stock_symbol
from vnpy_ashare.config import _CN_NAME_TO_EXCHANGE, exchange_to_cn
from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.storage.app_db import load_watchlist_rows
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
) -> AiContextData:
    """组装看盘页 AI 上下文（含行情摘要与本地 K 线条数）。"""
    if item is None:
        return AiContextData(page=page)

    extra_parts: list[str] = []
    if bar_count > 0:
        extra_parts.append(f"本地日 K 条数：{bar_count}")
    else:
        extra_parts.append("本地日 K：暂无（需先下载）")

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
        f'请调用 diagnose_stock(symbol="{vt_symbol}") 获取通达信问小达诊断数据（行情、技术指标、财务、资金流、研报），'
        "基于工具返回结果解读，不要编造未在结果中的指标或研报观点。"
    )


def build_technical_ai_prompt(vt_symbol: str, name: str = "") -> str:
    """生成技术形态分析预填文案（调用 technical_snapshot）。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return f'请分析 {title} 的近期技术形态。请调用 technical_snapshot(symbol="{vt_symbol}")，基于工具返回的均线、量比、区间涨跌等数据做解读。'


def build_signals_ai_prompt(vt_symbol: str, name: str = "") -> str:
    """生成双均线策略信号分析预填文案（调用 list_strategy_signals）。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return (
        f'请分析 {title} 的双均线（MA10/MA20）策略信号。请调用 list_strategy_signals(symbol="{vt_symbol}")，基于工具返回的金叉/死叉信号和当前均线状态做解读。'
    )


def build_historical_ai_prompt(
    vt_symbol: str,
    name: str = "",
    *,
    lookback: int = 20,
) -> str:
    """生成历史走势统计预填文案（调用 historical_pattern_summary，禁止预测）。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return (
        f"请分析 {title} 的近 {int(lookback)} 日走势。"
        f'请调用 historical_pattern_summary(symbol="{vt_symbol}", lookback={int(lookback)})，'
        "基于工具返回的涨跌幅、波动、连涨连跌等历史统计数据做描述，禁止预测未来走势。"
    )


def build_trend_ai_prompt(vt_symbol: str, name: str = "") -> str:
    """近 20 日走势快捷入口（``build_historical_ai_prompt`` 默认 lookback）。"""
    return build_historical_ai_prompt(vt_symbol, name, lookback=20)


def build_stock_completion_items(
    symbol: str,
    *,
    exchange_cn: str = "",
    name: str = "",
) -> list[StockCompletionItem]:
    """输入框联想项：诊断 / 技术面 / 双均线 / 近期走势。"""
    vt = resolve_vt_symbol(symbol, exchange_cn)
    display = name or symbol
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
                    f"{prefix}请调用 mcp_tdx_tdx_wenda_quotes 查询市盈率、ROE 等财务估值指标，"
                    f'必要时结合 diagnose_stock(symbol="{vt}")，'
                    "基于工具返回解读，禁止编造。"
                ),
            ),
            QuickAction(
                id="diagnose_report",
                label="研报评级",
                prompt=(f'{prefix}请通过问小达查询最新研报与评级，必要时结合 diagnose_stock(symbol="{vt}")，引用须注明来源与日期。'),
            ),
            QuickAction(
                id="diagnose_flow",
                label="资金流向",
                prompt=(f"{prefix}请调用 mcp_tdx_tdx_wenda_quotes 查询主力资金流向，基于返回数据描述资金面，禁止编造。"),
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
                prompt=(f"{prefix}请调用 mcp_tdx_tdx_wenda_quotes 查询 MACD、KDJ、RSI 等技术指标，基于返回数据做技术解读，非买卖建议。"),
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


def build_trend_forecast_menu(binding: StockBinding) -> QuickAction:
    """走势预测二级菜单（情景分析，非确定性买卖建议）。"""
    prefix = _wenda_prefix(binding)
    vt = binding.vt_symbol
    return QuickAction(
        id="trend_forecast",
        label="走势预测",
        tooltip=binding.tooltip,
        children=[
            QuickAction(
                id="trend_price",
                label="股价预测",
                prompt=(
                    f"{prefix}请调用 mcp_tdx_tdx_wenda_quotes 查询技术位与量价，"
                    f'必要时结合 diagnose_stock(symbol="{vt}")，'
                    "给出可能的股价波动区间情景分析（概率表述，非确定性预测），注明数据来源，禁止给出买卖价位。"
                ),
            ),
            QuickAction(
                id="trend_support",
                label="支撑压力位",
                prompt=(f"{prefix}请通过通达信问小达（mcp_tdx_tdx_wenda_quotes）查询该票支撑压力位、均线与关键价位，列出价位及依据，禁止编造。"),
            ),
            QuickAction(
                id="trend_5d",
                label="5日走势预测",
                prompt=(f"{prefix}请结合问小达获取近5日走势、MACD/KDJ/RSI 与量比，描述短期动能并给出未来5个交易日的可能情景（场景分析，非买卖建议）。"),
            ),
            QuickAction(
                id="trend_direction",
                label="方向预测",
                prompt=(f"{prefix}请基于问小达的技术指标、均线排列与主力资金流向，分析短期多空方向倾向（倾向性判断 + 不确定性说明，非确定性预测）。"),
            ),
        ],
    )


def build_bound_stock_menus(binding: StockBinding) -> list[QuickAction]:
    """四组快捷菜单：综合诊断 / 技术形态 / 走势预测 / 近期走势。"""
    return [
        build_diagnose_menu(binding),
        build_technical_menu(binding),
        build_trend_forecast_menu(binding),
        build_recent_trend_menu(binding),
    ]


def build_sector_overview_prompt(vt_symbol: str, name: str = "") -> str:
    """市场页：所属板块/概念行业联动分析预填文案。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return (
        f"请分析 {title} 所属板块/概念行业的近期表现与联动逻辑。"
        "可调用 mcp_tdx_tdx_wenda_quotes 查询板块关联、成分股联动与主力资金流向，"
        "基于工具返回解读，禁止编造未在结果中的板块数据。"
    )


def build_bar_health_prompt(vt_symbol: str, name: str = "", extra: str = "") -> str:
    """本地页：日 K 覆盖/过期/断层检查预填文案（调用 get_bars_summary）。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    context = f"当前上下文：{extra.strip()}\n" if extra.strip() else ""
    return (
        f"{context}请检查 {title} 的本地日 K 覆盖是否完整、是否过期或存在断层。"
        f'请调用 get_bars_summary(symbol="{vt_symbol}") 获取起止日期与条数，'
        "结合上下文说明数据健康状态，并给出补全或重下建议（不要直接执行下载）。"
    )


def build_add_watchlist_prompt(vt_symbol: str, name: str = "") -> str:
    """非自选页：加入自选池预填文案（调用 add_to_watchlist）。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return f'请将 {title} 加入自选池。请调用 add_to_watchlist(symbol="{vt_symbol}")，根据工具返回告知是否成功。'


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
    if page == "市场":
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
    extra = f" {detail}" if detail else ""
    return (
        f"请按「{pattern}」在 A 股全市场选股。{extra}"
        "直接调用 screen_by_pattern 执行（无需 propose_screening 确认）；"
        "结果用 Markdown 表格展示 Top 20，注明 pattern_score 与数据来源（本地日 K / 行情）。"
    )


def _screening_prompt(intent: str, *, detail: str = "") -> str:
    extra = f" {detail}" if detail else ""
    return (
        f"请按「{intent}」在 A 股中选股。{extra}"
        "先 list_screeners 了解终端内置方案；"
        "内置 preset 且条件明确时直接 screen_by_condition；"
        "形态选股（老鸭头/均线多头/W底/主题投资）直接 screen_by_pattern；"
        "已保存方案或复杂条件用 propose_screening。"
        "结果用 Markdown 表格展示，默认 Top 20，排除 ST，注明数据来源。"
    )


def build_pattern_screen_menu() -> QuickAction:
    """全市场形态选股二级菜单（老鸭头 / 均线多头 / W底 / 主题）。"""
    return QuickAction(
        id="pattern_screen",
        label="形态选股",
        tooltip="A 股全市场形态选股",
        children=[
            QuickAction(
                id="pattern_old_duck",
                label="老鸭头形态",
                prompt=_pattern_screen_prompt(
                    "老鸭头形态",
                    detail="关注放量突破、短期均线回踩后再次上攻、颈线位突破等典型特征。",
                ),
            ),
            QuickAction(
                id="pattern_ma_bull",
                label="均线多头",
                prompt=_pattern_screen_prompt(
                    "均线多头排列",
                    detail="优先 MA5>MA10>MA20>MA60，现价站上关键均线，量能配合。",
                ),
            ),
            QuickAction(
                id="pattern_w_bottom",
                label="W底形态",
                prompt=_pattern_screen_prompt(
                    "W底形态",
                    detail="关注双底结构、第二次探底缩量、突破颈线位放量等特征。",
                ),
            ),
            QuickAction(
                id="pattern_theme",
                label="主题投资",
                prompt=_pattern_screen_prompt(
                    "主题投资",
                    detail="结合当前热点主题/概念板块，筛选资金关注度高的龙头与跟风标的。",
                ),
            ),
        ],
    )


def build_condition_screen_menu() -> QuickAction:
    """全市场条件选股二级菜单（中线 / 短线 / 长线）。"""
    return QuickAction(
        id="condition_screen",
        label="条件选股",
        tooltip="A 股全市场条件选股",
        children=[
            QuickAction(
                id="cond_mid_swing",
                label="中线波段",
                prompt=_screening_prompt(
                    "中线波段",
                    detail="持有周期数周至数月，兼顾趋势与估值，关注中期均线支撑与波段空间。",
                ),
            ),
            QuickAction(
                id="cond_short_hot",
                label="短线游资",
                prompt=_screening_prompt(
                    "短线游资",
                    detail="关注涨停、连板、龙虎榜、主力净流入、高换手与题材活跃度。",
                ),
            ),
            QuickAction(
                id="cond_long_value",
                label="长线价投",
                prompt=_screening_prompt(
                    "长线价投",
                    detail="低估值、高 ROE、稳定现金流、合理 PE/PB，适合长期持有研究。",
                ),
            ),
        ],
    )


def build_reference_screen_menu() -> QuickAction:
    """参考策略选股二级菜单（波段 / 价值 / 成长 / 周期）。"""
    return QuickAction(
        id="reference_screen",
        label="参考选股",
        tooltip="A 股参考策略选股",
        children=[
            QuickAction(
                id="ref_short_swing",
                label="短线波段",
                prompt=_screening_prompt(
                    "短线波段",
                    detail="1-2 周级别的趋势或反弹机会，关注量价配合与技术位。",
                ),
            ),
            QuickAction(
                id="ref_long_value",
                label="长线价值",
                prompt=_screening_prompt(
                    "长线价值",
                    detail="护城河、分红、低负债、业绩稳定的价值型标的。",
                ),
            ),
            QuickAction(
                id="ref_growth",
                label="成长赛道",
                prompt=_screening_prompt(
                    "成长赛道",
                    detail="高景气行业龙头，营收/利润增速较好，关注赛道逻辑与估值匹配度。",
                ),
            ),
            QuickAction(
                id="ref_cyclical",
                label="周期资源",
                prompt=_screening_prompt(
                    "周期资源",
                    detail="商品/资源/周期板块，关注景气度、库存周期与龙头弹性。",
                ),
            ),
        ],
    )


def build_assistant_screening_menus() -> list[QuickAction]:
    """全屏助手专用：形态/条件/参考选股（全市场，不绑定单票）。"""
    return [
        build_pattern_screen_menu(),
        build_condition_screen_menu(),
        build_reference_screen_menu(),
    ]


def build_assistant_quick_actions() -> list[QuickAction]:
    """全屏 AI 助手：单票分析菜单 + 全市场选股菜单。"""
    return [
        *build_bound_stock_menus(resolve_assistant_stock_binding()),
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
