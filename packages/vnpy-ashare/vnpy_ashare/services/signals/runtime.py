"""策略信号盘中修饰、锚点估算与列表展示（依赖 QuoteSnapshot）。"""

from __future__ import annotations

from vnpy_ashare.domain.signal_snapshot import (
    INTRADAY_ANCHOR_MIN_DELTA,
    INTRADAY_CROSS_NEAR_PCT,
    SIGNAL_BENCHMARK_LOOKBACK,
    SIGNAL_RECENT_DAYS,
    SignalKind,
    SignalSnapshot,
    dist_anchor_exceeds_warn,
    dist_buy_pct,
    dist_sell_pct,
    ma_gap_pct,
    signal_age_days,
    signal_as_of_stale,
    signal_expired,
    signal_missing_kline,
    signal_sort_key,
)
from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot


def structure_broken(
    snapshot: SignalSnapshot,
    *,
    quote: QuoteSnapshot | None = None,
    slow_window: int = 20,
    fast_window: int = 10,
) -> bool:
    """买入信号下现价是否跌破结构支撑锚点。"""
    if snapshot.signal != "buy" or signal_missing_kline(snapshot):
        return False
    last_price = quote.last_price if quote and quote.last_price > 0 else snapshot.last_close
    if last_price is None:
        return False
    display_buy, _, _ = resolve_display_anchor_prices(
        snapshot,
        quote=quote,
        slow_window=slow_window,
        fast_window=fast_window,
    )
    anchor = display_buy if display_buy is not None else snapshot.ref_buy_price
    if anchor is None:
        return False
    return last_price < anchor


def resolve_ma_gap_pct(
    snapshot: SignalSnapshot,
    *,
    quote: QuoteSnapshot | None = None,
    slow_window: int = 20,
    fast_window: int = 10,
) -> float | None:
    """列表展示用快慢间距；有行情时优先盘中估算。"""
    fast_est, slow_est = _resolve_intraday_ma_pair(
        snapshot,
        quote=quote,
        slow_window=slow_window,
        fast_window=fast_window,
    )
    if fast_est is not None and slow_est is not None:
        return ma_gap_pct(fast_est, slow_est)
    if snapshot.ma_gap_pct is not None:
        return snapshot.ma_gap_pct
    return ma_gap_pct(snapshot.fast_ma, snapshot.slow_ma)


def format_signal_label_display(
    snapshot: SignalSnapshot,
    *,
    bar_end_date: str | None = None,
    recent_days: int = SIGNAL_RECENT_DAYS,
    quote: QuoteSnapshot | None = None,
    slow_window: int = 20,
    fast_window: int = 10,
) -> str:
    """信号列文案（含 K 线 stale / 信号过期 / 结构破坏徽章）。"""
    badges: list[str] = []
    if bar_end_date and signal_as_of_stale(snapshot, bar_end_date=bar_end_date):
        badges.append("K旧")
    if signal_expired(snapshot, recent_days=recent_days):
        badges.append("过期")
    if structure_broken(
        snapshot,
        quote=quote,
        slow_window=slow_window,
        fast_window=fast_window,
    ):
        badges.append("破")
    if not badges:
        return snapshot.signal_label
    return f"{snapshot.signal_label}·{'·'.join(badges)}"


def format_strength_breakdown(snapshot: SignalSnapshot | None) -> str:
    """强度列 tooltip：综合分与各分项权重。"""
    if snapshot is None or snapshot.strength is None:
        return ""
    lines = [f"综合强度：{snapshot.strength:.0f}"]
    parts: list[str] = []
    if snapshot.strength_cross is not None:
        parts.append(f"交叉 {snapshot.strength_cross:.0f}×40%")
    if snapshot.strength_alignment is not None:
        parts.append(f"排列 {snapshot.strength_alignment:.0f}×25%")
    if snapshot.strength_volume is not None:
        parts.append(f"量比 {snapshot.strength_volume:.0f}×20%")
    if snapshot.strength_pattern is not None:
        parts.append(f"形态 {snapshot.strength_pattern:.0f}×15%")
    if parts:
        lines.append("分项：" + " · ".join(parts))
    return "\n".join(lines)


def estimate_adjusted_ma_anchor(
    ma_anchor: float | None,
    bar_close: float | None,
    last_price: float | None,
    window: int,
) -> float | None:
    """用现价替换末根收盘，线性估算均线锚点（盘中参考）。"""
    if ma_anchor is None or bar_close is None or last_price is None or window <= 0:
        return None
    return round(ma_anchor + (last_price - bar_close) / window, 2)


def resolve_display_anchor_prices(
    snapshot: SignalSnapshot,
    *,
    quote: QuoteSnapshot | None = None,
    slow_window: int = 20,
    fast_window: int = 10,
) -> tuple[float | None, float | None, bool]:
    """列表/图表展示用支撑/阻力锚点；有行情时用现价估算盘中均线。"""
    last_price = quote.last_price if quote and quote.last_price > 0 else None
    bar_close = snapshot.last_close
    if last_price is None or bar_close is None:
        return snapshot.ref_buy_price, snapshot.ref_sell_price, False

    buy = estimate_adjusted_ma_anchor(
        snapshot.ref_buy_price,
        bar_close,
        last_price,
        slow_window,
    )
    sell = estimate_adjusted_ma_anchor(
        snapshot.ref_sell_price,
        bar_close,
        last_price,
        fast_window,
    )
    display_buy = buy if buy is not None else snapshot.ref_buy_price
    display_sell = sell if sell is not None else snapshot.ref_sell_price
    adjusted = False
    if display_buy is not None and snapshot.ref_buy_price is not None and abs(display_buy - snapshot.ref_buy_price) >= INTRADAY_ANCHOR_MIN_DELTA:
        adjusted = True
    if display_sell is not None and snapshot.ref_sell_price is not None and abs(display_sell - snapshot.ref_sell_price) >= INTRADAY_ANCHOR_MIN_DELTA:
        adjusted = True
    return display_buy, display_sell, adjusted


def format_signal_context_extra(
    snapshot: SignalSnapshot,
    *,
    quote: QuoteSnapshot | None = None,
    slow_window: int = 20,
    fast_window: int = 10,
) -> str:
    """格式化策略信号摘要，供 AI 上下文或预填问句附加。"""
    if signal_missing_kline(snapshot) or snapshot.signal == "na":
        return ""

    lines = [f"策略信号：{snapshot.signal_label}"]
    if snapshot.signal_date:
        lines.append(f"信号日：{snapshot.signal_date}")
    if snapshot.as_of:
        lines.append(f"K 线截止：{snapshot.as_of}")

    list_buy, list_sell = resolve_list_ref_prices(
        snapshot,
        quote=quote,
        slow_window=slow_window,
        fast_window=fast_window,
    )
    if snapshot.ref_buy_price is not None:
        lines.append(f"支撑锚点：{snapshot.ref_buy_price:.2f}")
    if snapshot.ref_sell_price is not None:
        lines.append(f"阻力锚点：{snapshot.ref_sell_price:.2f}")
    if list_buy is not None:
        lines.append(f"参考买价：{list_buy:.2f}")
    if list_sell is not None:
        lines.append(f"参考卖价：{list_sell:.2f}")
    last_price = quote.last_price if quote and quote.last_price > 0 else None
    pct = dist_buy_pct(list_buy, last_price)
    if pct is not None:
        lines.append(f"距买价%：{pct:+.2f}")
    sell_pct = dist_sell_pct(list_sell, last_price)
    if sell_pct is not None:
        lines.append(f"距卖价%：{sell_pct:+.2f}")
    if snapshot.relative_index_pct is not None:
        lines.append(f"相对300%（{SIGNAL_BENCHMARK_LOOKBACK}日）：{snapshot.relative_index_pct:+.2f}")

    hints = build_runtime_signal_hints(
        snapshot,
        quote=quote,
        slow_window=slow_window,
        fast_window=fast_window,
    )
    if hints:
        lines.append("盘中提示：" + "；".join(hints))
    if snapshot.reason_summary:
        lines.append(f"理由：{snapshot.reason_summary}")
    return "\n".join(lines)


def _fallback_action_ref_prices(snapshot: SignalSnapshot) -> tuple[float | None, float | None]:
    """旧快照无动作参考价时回退到结构锚点。"""
    buy = snapshot.action_ref_buy_price
    sell = snapshot.action_ref_sell_price
    if buy is None:
        buy = snapshot.ref_buy_price
    if sell is None:
        sell = snapshot.ref_sell_price
    return buy, sell


def resolve_list_ref_prices(
    snapshot: SignalSnapshot,
    *,
    quote: QuoteSnapshot | None = None,
    slow_window: int = 20,
    fast_window: int = 10,
) -> tuple[float | None, float | None]:
    """列表展示用参考买/卖价（动作位 + 实时行情修饰）。"""
    del slow_window, fast_window
    action_buy, action_sell = _fallback_action_ref_prices(snapshot)
    last_price = quote.last_price if quote and quote.last_price > 0 else None
    if last_price is None:
        return action_buy, action_sell

    if snapshot.signal == "buy":
        if action_buy is not None:
            action_buy = round(min(action_buy, last_price), 2)
    elif snapshot.signal == "sell":
        action_sell = round(last_price, 2)
    elif snapshot.signal == "hold":
        if action_buy is not None:
            action_buy = round(min(action_buy, last_price), 2)
        if action_sell is not None:
            action_sell = round(max(action_sell, last_price), 2)
    return action_buy, action_sell


def build_price_field_explanations(
    signal: SignalKind,
    *,
    fast_window: int,
    slow_window: int,
) -> tuple[str, ...]:
    """理由弹窗中的字段释义（按当前信号态）。"""
    anchor_buy = f"支撑锚点：日 K 慢线 MA{slow_window} 结构位，反映均线支撑/跌破水平，用于判断结构是否破坏，非直接买卖价。"
    anchor_sell = f"阻力锚点：日 K 快线 MA{fast_window} 与近高形成的结构阻力，用于观察反弹压力，非直接买卖价。"
    if signal == "buy":
        ref_buy = f"参考买价：买入信号下的动作参考，取 min(金叉价/慢{slow_window}/收盘/现价) 偏低吸；有实时行情时纳入现价。"
        ref_sell = "参考卖价：买入信号下的止盈阻力参考，取近高与快线阻力区间的较低值。"
    elif signal == "sell":
        ref_buy = "参考买价：卖出信号下的回补参考，取近 20 日低或现价下方，表示若反弹回落可关注的位置，非当前结构慢线。"
        ref_sell = f"参考卖价：卖出信号下的离场参考，有行情时取现价，否则取 max(收盘/快{fast_window}) 反弹减仓位。"
    elif signal == "hold":
        ref_buy = f"参考买价：观望下的回踩关注位，取 min(慢{slow_window}/收盘/现价)。"
        ref_sell = f"参考卖价：观望下的反弹关注位，取 max(快{fast_window}/收盘/现价)。"
    else:
        ref_buy = "参考买价：数据不足时无法计算。"
        ref_sell = "参考卖价：数据不足时无法计算。"
    dist = "距买价%：现价相对参考买价（动作位）的偏离百分比。"
    dist_sell = "距卖价%：现价相对参考卖价（动作位）的偏离百分比。"
    return (anchor_buy, anchor_sell, ref_buy, ref_sell, dist, dist_sell)


def _resolve_intraday_ma_pair(
    snapshot: SignalSnapshot,
    *,
    quote: QuoteSnapshot | None,
    slow_window: int,
    fast_window: int,
) -> tuple[float | None, float | None]:
    """用现价估算盘中快慢均线（虚拟末根 K）。"""
    last_price = quote.last_price if quote and quote.last_price > 0 else None
    bar_close = snapshot.last_close
    if last_price is None or bar_close is None:
        return None, None

    fast_base = snapshot.fast_ma if snapshot.fast_ma is not None else snapshot.ref_sell_price
    slow_base = snapshot.slow_ma if snapshot.slow_ma is not None else snapshot.ref_buy_price
    fast_est = estimate_adjusted_ma_anchor(fast_base, bar_close, last_price, fast_window)
    slow_est = estimate_adjusted_ma_anchor(slow_base, bar_close, last_price, slow_window)
    return fast_est, slow_est


def build_intraday_cross_hints(
    snapshot: SignalSnapshot,
    *,
    quote: QuoteSnapshot | None = None,
    slow_window: int = 20,
    fast_window: int = 10,
    near_pct: float = INTRADAY_CROSS_NEAR_PCT,
) -> tuple[str, ...]:
    """虚拟末根 K 估算快慢线间距，提示接近金叉/死叉（不改变缓存信号）。"""
    if snapshot.signal == "na" or signal_missing_kline(snapshot):
        return ()

    fast_est, slow_est = _resolve_intraday_ma_pair(
        snapshot,
        quote=quote,
        slow_window=slow_window,
        fast_window=fast_window,
    )
    if fast_est is None or slow_est is None or slow_est <= 0:
        return ()

    gap = fast_est - slow_est
    gap_pct = gap / slow_est * 100
    hints: list[str] = []
    if gap > 0:
        if snapshot.signal == "sell":
            hints.append("盘中估算：虚拟金叉（快线已上穿慢线），与卖出信号背离")
        elif abs(gap_pct) <= near_pct:
            hints.append(f"盘中估算：快慢线刚金叉（间距 {gap_pct:+.2f}%）")
        elif snapshot.signal == "hold":
            hints.append(f"盘中估算：快线高于慢线 {gap_pct:+.2f}%")
    elif gap < 0:
        if snapshot.signal == "buy":
            hints.append("盘中估算：虚拟死叉（快线已下穿慢线），与买入信号背离")
        elif abs(gap_pct) <= near_pct:
            hints.append(f"盘中估算：距虚拟金叉约 {abs(gap_pct):.2f}%")
        elif snapshot.signal == "hold":
            hints.append(f"盘中估算：距虚拟金叉约 {abs(gap_pct):.2f}%")
    else:
        hints.append("盘中估算：快慢线重合，临界交叉")
    return tuple(hints)


def build_runtime_signal_hints(
    snapshot: SignalSnapshot,
    *,
    quote: QuoteSnapshot | None = None,
    slow_window: int = 20,
    fast_window: int = 10,
    recent_days: int = SIGNAL_RECENT_DAYS,
) -> tuple[str, ...]:
    """结合实时行情生成盘中提示（不写入缓存快照）。"""
    if snapshot.signal == "na" or signal_missing_kline(snapshot):
        return ()

    hints: list[str] = []
    last_price = quote.last_price if quote and quote.last_price > 0 else None

    if snapshot.signal in ("buy", "sell"):
        age = signal_age_days(snapshot)
        if age is not None and age > max(0, int(recent_days)):
            hints.append(f"信号已过期（{age} 天前），仅供历史参考")

    pct = dist_buy_pct(snapshot.ref_buy_price, last_price)
    if pct is not None and dist_anchor_exceeds_warn(snapshot.ref_buy_price, last_price):
        hints.append(f"现价偏离支撑锚点 {pct:+.2f}%")
    if snapshot.signal == "sell" and pct is not None and pct < 0:
        hints.append("现价已跌破慢线支撑")
    if structure_broken(
        snapshot,
        quote=quote,
        slow_window=slow_window,
        fast_window=fast_window,
    ):
        hints.append("结构破坏：现价已跌破支撑锚点")

    action_buy, action_sell = resolve_list_ref_prices(
        snapshot,
        quote=quote,
        slow_window=slow_window,
        fast_window=fast_window,
    )
    action_pct = dist_buy_pct(action_buy, last_price)
    if action_pct is not None and dist_anchor_exceeds_warn(action_buy, last_price):
        hints.append(f"现价偏离参考买价 {action_pct:+.2f}%")
    if snapshot.signal == "sell" and action_sell is not None and last_price is not None:
        if last_price <= action_sell * 1.002:
            hints.append("现价接近参考卖价（离场动作区）")

    hints.extend(
        build_intraday_cross_hints(
            snapshot,
            quote=quote,
            slow_window=slow_window,
            fast_window=fast_window,
        )
    )
    return tuple(hints)


def signal_cell_text(
    column_key: str,
    snapshot: SignalSnapshot | None,
    *,
    quote: QuoteSnapshot | None = None,
    bar_end_date: str | None = None,
    slow_window: int = 20,
    fast_window: int = 10,
) -> tuple[str, float | str]:
    if snapshot is None:
        return "—", float("-inf")

    list_ref_buy, list_ref_sell = resolve_list_ref_prices(
        snapshot,
        quote=quote,
        slow_window=slow_window,
        fast_window=fast_window,
    )

    if column_key == "signal":
        text = format_signal_label_display(
            snapshot,
            bar_end_date=bar_end_date,
            quote=quote,
            slow_window=slow_window,
            fast_window=fast_window,
        )
        return text, signal_sort_key(snapshot.signal)
    if column_key == "signal_age":
        if snapshot.signal not in ("buy", "sell"):
            return "—", float("-inf")
        age = signal_age_days(snapshot)
        if age is None:
            return "—", float("-inf")
        return f"{age}天", age
    if column_key == "volume_ratio":
        ratio = snapshot.volume_ratio_5d
        if ratio is None:
            return "—", float("-inf")
        return f"{ratio:.2f}", ratio
    if column_key == "ma_gap_pct":
        gap = resolve_ma_gap_pct(
            snapshot,
            quote=quote,
            slow_window=slow_window,
            fast_window=fast_window,
        )
        if gap is None:
            return "—", float("-inf")
        return f"{gap:+.2f}", gap
    if column_key == "signal_date":
        text = snapshot.signal_date or "—"
        return text, text
    if column_key == "anchor_buy":
        display_buy, _, adjusted = resolve_display_anchor_prices(
            snapshot,
            quote=quote,
            slow_window=slow_window,
            fast_window=fast_window,
        )
        if display_buy is None:
            return "—", float("-inf")
        text = f"{display_buy:.2f}*" if adjusted else f"{display_buy:.2f}"
        return text, display_buy
    if column_key == "anchor_sell":
        _, display_sell, adjusted = resolve_display_anchor_prices(
            snapshot,
            quote=quote,
            slow_window=slow_window,
            fast_window=fast_window,
        )
        if display_sell is None:
            return "—", float("-inf")
        text = f"{display_sell:.2f}*" if adjusted else f"{display_sell:.2f}"
        return text, display_sell
    if column_key == "ref_buy_price":
        if list_ref_buy is None:
            return "—", float("-inf")
        return f"{list_ref_buy:.2f}", list_ref_buy
    if column_key == "ref_sell_price":
        if list_ref_sell is None:
            return "—", float("-inf")
        return f"{list_ref_sell:.2f}", list_ref_sell
    if column_key == "dist_buy_pct":
        pct = dist_buy_pct(list_ref_buy, quote.last_price if quote else None)
        if pct is None:
            return "—", float("-inf")
        return f"{pct:+.2f}", pct
    if column_key == "dist_sell_pct":
        pct = dist_sell_pct(list_ref_sell, quote.last_price if quote else None)
        if pct is None:
            return "—", float("-inf")
        return f"{pct:+.2f}", pct
    if column_key == "relative_index_pct":
        excess = snapshot.relative_index_pct
        if excess is None:
            return "—", float("-inf")
        return f"{excess:+.2f}", excess
    if column_key == "signal_strength":
        if snapshot.strength is None:
            return "—", float("-inf")
        return f"{snapshot.strength:.0f}", snapshot.strength
    if column_key == "signal_reason":
        text = snapshot.reason_summary or "—"
        return text, text
    return "—", float("-inf")


def signal_cell_color(
    column_key: str,
    snapshot: SignalSnapshot | None,
    *,
    colors,
    quote: QuoteSnapshot | None = None,
    bar_end_date: str | None = None,
    warning_color: str | None = None,
    slow_window: int = 20,
    fast_window: int = 10,
) -> str | None:
    if snapshot is None:
        return None
    if column_key == "signal":
        if snapshot.signal == "buy":
            base = colors.rise
        elif snapshot.signal == "sell":
            base = colors.fall
        else:
            base = None
        if warning_color and (
            (bar_end_date and signal_as_of_stale(snapshot, bar_end_date=bar_end_date))
            or signal_expired(snapshot)
            or structure_broken(
                snapshot,
                quote=quote,
                slow_window=slow_window,
                fast_window=fast_window,
            )
        ):
            return warning_color
        return base
    if column_key == "signal_age" and warning_color:
        if signal_expired(snapshot):
            return warning_color
    if column_key == "volume_ratio" and warning_color:
        ratio = snapshot.volume_ratio_5d
        if ratio is not None and (ratio >= 1.5 or ratio <= 0.8):
            return warning_color
    if column_key == "dist_buy_pct" and warning_color:
        last_price = quote.last_price if quote else None
        list_ref_buy, _ = resolve_list_ref_prices(
            snapshot,
            quote=quote,
            slow_window=slow_window,
            fast_window=fast_window,
        )
        if dist_anchor_exceeds_warn(list_ref_buy, last_price):
            return warning_color
        if structure_broken(
            snapshot,
            quote=quote,
            slow_window=slow_window,
            fast_window=fast_window,
        ):
            return warning_color
    if column_key == "dist_sell_pct" and warning_color:
        last_price = quote.last_price if quote else None
        _, list_ref_sell = resolve_list_ref_prices(
            snapshot,
            quote=quote,
            slow_window=slow_window,
            fast_window=fast_window,
        )
        if dist_anchor_exceeds_warn(list_ref_sell, last_price):
            return warning_color
    if column_key == "anchor_buy" and warning_color:
        if structure_broken(
            snapshot,
            quote=quote,
            slow_window=slow_window,
            fast_window=fast_window,
        ):
            return warning_color
    if column_key == "relative_index_pct":
        excess = snapshot.relative_index_pct
        if excess is None:
            return None
        if excess >= 2:
            return colors.rise
        if excess <= -2:
            return colors.fall
    return None
