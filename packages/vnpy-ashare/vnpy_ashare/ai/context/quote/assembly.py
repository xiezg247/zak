"""行情 AI 上下文组装：AiContextData、标的绑定、快捷菜单与动作。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.ai.context.quote.format import format_quote_summary
from vnpy_ashare.ai.context.quote.prompts import (
    build_add_watchlist_prompt,
    build_bar_health_prompt,
    build_diagnose_ai_prompt,
    build_historical_ai_prompt,
    build_positions_ai_prompt,
    build_reference_peer_prompt,
    build_sector_overview_prompt,
    build_signals_ai_prompt,
    build_technical_ai_prompt,
    build_trend_ai_prompt,
    build_trend_scenario_ai_prompt,
    pattern_screen_prompt,
    preset_screen_prompt,
    recipe_screen_prompt,
    resolve_signal_prompt_params,
)
from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.config import _CN_NAME_TO_EXCHANGE, exchange_to_cn
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.storage.repositories.positions import position_contains
from vnpy_ashare.storage.repositories.watchlist import load_watchlist_rows
from vnpy_common.ai.protocol import AiContextData, QuickAction, StockCompletionItem


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
    """综合诊断二级菜单（全量 / 财务 / 资金流）。"""
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
                prompt=(f"{prefix}请查询市盈率、ROE 等财务估值指标，必要时结合综合诊断，基于返回结果解读，禁止编造。"),
            ),
            QuickAction(
                id="diagnose_flow",
                label="资金流向",
                prompt=(f"{prefix}请查询主力资金流向，基于返回数据描述资金面，禁止编造。"),
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
                prompt=(f"{prefix}请查询 MACD、KDJ、RSI 等技术指标，基于返回数据做技术解读，非买卖建议。"),
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
    """走势预测二级菜单（本地情景摘要，非确定性买卖建议）。"""
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
        tooltip=f"{binding.tooltip} · 本地结构 · 情景分析",
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


def is_symbol_in_positions(vt_symbol: str) -> bool:
    """判断标的是否已登记持仓记账。"""
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


def build_pattern_screen_menu() -> QuickAction:
    """全市场形态选股二级菜单（老鸭头 / 均线多头 / W底 / 热点活跃）。"""
    return QuickAction(
        id="pattern_screen",
        label="形态选股",
        tooltip="全市场形态扫描，不可用时降级本地日 K",
        children=[
            QuickAction(
                id="pattern_old_duck",
                label="老鸭头形态",
                auto_send=True,
                prompt=pattern_screen_prompt(
                    "老鸭头形态",
                    detail="关注放量突破、短期均线回踩后再次上攻。",
                ),
            ),
            QuickAction(
                id="pattern_ma_bull",
                label="均线多头",
                auto_send=True,
                prompt=pattern_screen_prompt(
                    "均线多头排列",
                    detail="优先 MA5>MA10>MA20>MA60，现价站上关键均线。",
                ),
            ),
            QuickAction(
                id="pattern_w_bottom",
                label="W底形态",
                auto_send=True,
                prompt=pattern_screen_prompt(
                    "W底形态",
                    detail="关注双底结构、第二次探底缩量、突破颈线放量。",
                ),
            ),
            QuickAction(
                id="pattern_theme",
                label="热点活跃",
                auto_send=True,
                tooltip="全市场行情筛选，非 K 线形态；需行情采集",
                prompt=pattern_screen_prompt(
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
                prompt=recipe_screen_prompt(
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
                prompt=recipe_screen_prompt(
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
                prompt=preset_screen_prompt(
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
                prompt=preset_screen_prompt(
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
                prompt=preset_screen_prompt(
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
