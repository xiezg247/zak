"""AI 预填 prompt 模板与信号区策略参数读取。"""

from __future__ import annotations

_TREND_SCENARIO_OUTPUT = (
    "按乐观/基准/悲观三情景输出（概率表述 + 触发/失效条件）。"
    "本地情景摘要已含技术面与方向提示，数据充分时直接作答，勿重复拉取行情或策略信号；"
    "禁止确定性预测与具体买卖价位。"
)


def resolve_signal_prompt_params() -> tuple[str, int, int]:
    """读取自选页信号区策略参数（与信号面板设置一致）。"""
    try:
        from vnpy_ashare.config.preferences import load_watchlist_signal_config

        cfg = load_watchlist_signal_config()
        return cfg.class_name, cfg.fast_window, cfg.slow_window
    except Exception:
        return "AshareDoubleMaStrategy", 10, 20


def build_diagnose_ai_prompt(vt_symbol: str, name: str = "") -> str:
    """生成跳转 AI 助手页的综合诊断预填文案。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return (
        f"请对 {title} 做综合诊断。"
        "请按需调用问小达/通达信 MCP 与本地工具，获取行情、技术指标、财务、资金流等数据；"
        "结合下方已知本地摘要解读，不要编造未在工具结果中的指标。"
    )


def build_technical_ai_prompt(vt_symbol: str, name: str = "") -> str:
    """生成技术形态分析预填文案。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return f"请分析 {title} 的近期技术形态。涵盖均线排列、量比、区间涨跌等，基于实际数据做解读，不要编造。"


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
    return f"请分析 {title} 的双均线（MA{fast}/MA{slow}）策略信号。解读金叉/死叉信号与当前均线状态，基于实际数据，不要编造。"


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
        return f"{base}结合当前行情与信号区展示字段（参考价、距买价%）做研究解读，禁止给出具体买卖价或仓位建议。"
    return (
        f"已知信号区快照（规则计算，非买卖建议）：\n{snapshot_text}\n\n{base}结合上述快照与工具返回核对解读；盘中提示仅供参考，禁止给出具体买卖价或仓位建议。"
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
        "优先使用本地日 K 统计，本地不足时自动补充外部参考数据；"
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
    """走势预测快捷入口（本地情景摘要）。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    horizon = max(1, min(int(horizon_days or 5), 20))
    fast = max(2, int(fast_window or 10))
    slow = max(fast + 1, int(slow_window or 20))
    base = f"请对 {title} 做走势情景分析（非确定性预测，展望 {horizon} 日）。基于本地均线（MA{fast}/MA{slow}）、结构锚点与统计参考带组织分析。"
    focus_lines = {
        "price": "重点解读参考波动区间与结构锚点，给出可能的价位情景。",
        "support": "重点列出支撑/阻力锚点及距买/卖参考价的偏离。",
        "5d": f"重点结合短期动能与方向提示，描述 {horizon} 日可能情景。",
        "direction": "重点解读多空方向提示、均线排列与规则信号，给出倾向与不确定性说明。",
        "general": "综合技术面、动能、结构锚点与方向提示组织三情景。",
    }
    detail = focus_lines.get(focus, focus_lines["general"])
    return f"{base}{detail}{_TREND_SCENARIO_OUTPUT}"


def build_sector_overview_prompt(vt_symbol: str, name: str = "") -> str:
    """市场页：所属板块/概念行业联动分析预填文案。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return f"请分析 {title} 所属板块/概念行业的近期表现与联动逻辑。可查询板块关联、成分股联动与主力资金流向，基于返回数据解读，禁止编造未在结果中的板块数据。"


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


def pattern_screen_prompt(pattern: str, *, detail: str = "") -> str:
    detail_text = f"{detail} " if detail else ""
    return (
        f"请执行形态选股「{pattern}」。{detail_text}"
        "优先全市场形态扫描，不可用时降级本地日 K。"
        "完成后用 Markdown 表格展示 Top 20（含形态得分、形态说明、数据来源），"
        "并说明扫描范围。"
    )


def recipe_screen_prompt(
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


def preset_screen_prompt(
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


def screening_prompt(intent: str, *, detail: str = "") -> str:
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


def build_note_review_prompt(vt_symbol: str, name: str = "") -> str:
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return (
        f"请结合我对 {title} 的备忘、流水与历史分析报告（见终端上下文 extra，或调用 get_stock_notes / list_stock_analysis_reports / get_stock_analysis_report），"
        "做结构化复盘：核心逻辑是否仍成立、与当前行情的关系、需跟踪的风险点。"
        "仅供研究，不构成买卖建议。"
    )
