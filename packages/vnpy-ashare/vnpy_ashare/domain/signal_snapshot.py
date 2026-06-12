"""自选页策略信号快照（规则计算，非买卖建议）。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from vnpy_ashare.quotes.snapshot import QuoteSnapshot

SignalKind = Literal["buy", "sell", "hold", "na"]

SIGNAL_LABELS: dict[SignalKind, str] = {
    "buy": "买入",
    "sell": "卖出",
    "hold": "观望",
    "na": "—",
}

SIGNAL_COLUMN_KEYS: frozenset[str] = frozenset(
    {
        "signal",
        "signal_date",
        "ref_buy_price",
        "ref_sell_price",
        "dist_buy_pct",
        "signal_strength",
        "signal_reason",
    }
)

DIST_ANCHOR_WARN_PCT = 8.0
SIGNAL_RECENT_DAYS = 5
SIGNAL_STRENGTH_STRONG = 70.0
SIGNAL_BENCHMARK_SYMBOL = "000300"
SIGNAL_BENCHMARK_LOOKBACK = 20
INTRADAY_ANCHOR_MIN_DELTA = 0.01
INTRADAY_CROSS_NEAR_PCT = 0.5

_KLINE_WARNING_MARKERS = ("K 线不足", "暂无足够 K 线", "下载日 K")


def signal_missing_kline(snapshot: SignalSnapshot | None) -> bool:
    """快照是否因本地日 K 不足而无法计算。"""
    if snapshot is None or not snapshot.warnings:
        return False
    return any(any(marker in warning for marker in _KLINE_WARNING_MARKERS) for warning in snapshot.warnings)


def signal_as_of_stale(snapshot: SignalSnapshot | None, *, bar_end_date: str | None) -> bool:
    """快照 as_of 是否与本地日 K 最后交易日一致。"""
    if snapshot is None or signal_missing_kline(snapshot):
        return False
    if not snapshot.as_of:
        return True
    if not bar_end_date or bar_end_date == "—":
        return True
    return snapshot.as_of != bar_end_date


@dataclass(frozen=True)
class SignalSnapshot:
    vt_symbol: str
    strategy_id: str
    as_of: str
    signal: SignalKind
    signal_label: str
    signal_date: str | None
    ref_buy_price: float | None
    ref_sell_price: float | None
    strength: float | None
    reason_summary: str
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    last_close: float | None = None
    action_ref_buy_price: float | None = None
    action_ref_sell_price: float | None = None
    fast_ma: float | None = None
    slow_ma: float | None = None
    volume_ratio_5d: float | None = None
    ma_gap_pct: float | None = None
    strength_cross: float | None = None
    strength_alignment: float | None = None
    strength_volume: float | None = None
    strength_pattern: float | None = None
    relative_index_pct: float | None = None

    @property
    def tooltip(self) -> str:
        parts = list(self.reasons)
        if self.warnings:
            parts.extend(self.warnings)
        return "\n".join(part for part in parts if part)


def signal_snapshot_to_dict(snapshot: SignalSnapshot) -> dict[str, Any]:
    """序列化信号快照（供 AI 工具 JSON 返回）。"""
    return {
        "vt_symbol": snapshot.vt_symbol,
        "strategy_id": snapshot.strategy_id,
        "as_of": snapshot.as_of,
        "signal": snapshot.signal,
        "signal_label": snapshot.signal_label,
        "signal_date": snapshot.signal_date,
        "ref_buy_price": snapshot.ref_buy_price,
        "ref_sell_price": snapshot.ref_sell_price,
        "action_ref_buy_price": snapshot.action_ref_buy_price,
        "action_ref_sell_price": snapshot.action_ref_sell_price,
        "strength": snapshot.strength,
        "reason_summary": snapshot.reason_summary,
        "warnings": list(snapshot.warnings),
        "last_close": snapshot.last_close,
        "fast_ma": snapshot.fast_ma,
        "slow_ma": snapshot.slow_ma,
        "volume_ratio_5d": snapshot.volume_ratio_5d,
        "ma_gap_pct": snapshot.ma_gap_pct,
        "strength_cross": snapshot.strength_cross,
        "strength_alignment": snapshot.strength_alignment,
        "strength_volume": snapshot.strength_volume,
        "strength_pattern": snapshot.strength_pattern,
        "relative_index_pct": snapshot.relative_index_pct,
    }


_SIGNAL_TRANSITION_TRACKED = frozenset({"buy", "sell", "hold"})


def detect_signal_transitions(
    before: Mapping[str, SignalSnapshot | None],
    after: Mapping[str, SignalSnapshot],
    *,
    symbols: list[str] | None = None,
    name_for: Any | None = None,
) -> tuple[str, ...]:
    """检测信号状态变化，返回可读通知行。"""
    keys = symbols if symbols is not None else list(after)
    lines: list[str] = []
    for vt_symbol in keys:
        old = before.get(vt_symbol)
        new = after.get(vt_symbol)
        if old is None or new is None or signal_missing_kline(new):
            continue
        if old.signal == new.signal:
            continue
        if new.signal not in _SIGNAL_TRANSITION_TRACKED:
            continue
        if old.signal not in _SIGNAL_TRANSITION_TRACKED and new.signal == "hold":
            continue
        title = vt_symbol
        if name_for is not None:
            resolved = name_for(vt_symbol)
            if resolved:
                title = f"{resolved}（{vt_symbol}）"
        lines.append(f"{title}：{old.signal_label} → {new.signal_label}")
    return tuple(lines)


def dist_buy_pct(ref_buy_price: float | None, last_price: float | None) -> float | None:
    if ref_buy_price is None or last_price is None or ref_buy_price <= 0:
        return None
    return round((last_price - ref_buy_price) / ref_buy_price * 100, 2)


def dist_sell_pct(ref_sell_price: float | None, last_price: float | None) -> float | None:
    if ref_sell_price is None or last_price is None or ref_sell_price <= 0:
        return None
    return round((last_price - ref_sell_price) / ref_sell_price * 100, 2)


def dist_anchor_exceeds_warn(
    ref_buy_price: float | None,
    last_price: float | None,
    *,
    warn_pct: float = DIST_ANCHOR_WARN_PCT,
) -> bool:
    pct = dist_buy_pct(ref_buy_price, last_price)
    if pct is None:
        return False
    return abs(pct) >= warn_pct


def _parse_signal_date(value: str | None) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def signal_age_days(snapshot: SignalSnapshot) -> int | None:
    """信号日与 as_of 间隔（自然日）。"""
    signal_day = _parse_signal_date(snapshot.signal_date)
    as_of_day = _parse_signal_date(snapshot.as_of)
    if signal_day is None or as_of_day is None:
        return None
    return (as_of_day - signal_day).days


def signal_expired(snapshot: SignalSnapshot, *, recent_days: int = SIGNAL_RECENT_DAYS) -> bool:
    """买入/卖出信号是否已超过有效窗口。"""
    if snapshot.signal not in ("buy", "sell"):
        return False
    age = signal_age_days(snapshot)
    if age is None:
        return False
    return age > max(0, int(recent_days))


def signal_is_fresh(snapshot: SignalSnapshot, *, recent_days: int = SIGNAL_RECENT_DAYS) -> bool:
    """买入/卖出信号仍在有效窗口内。"""
    if snapshot.signal not in ("buy", "sell"):
        return False
    age = signal_age_days(snapshot)
    if age is None:
        return False
    return age <= max(0, int(recent_days))


def signal_is_strong(
    snapshot: SignalSnapshot,
    *,
    min_strength: float = SIGNAL_STRENGTH_STRONG,
) -> bool:
    """综合强度是否达到强信号阈值。"""
    return snapshot.strength is not None and snapshot.strength >= min_strength


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


def ma_gap_pct(fast_ma: float | None, slow_ma: float | None) -> float | None:
    """快慢均线间距占慢线比例（%）。"""
    if fast_ma is None or slow_ma is None or slow_ma <= 0:
        return None
    return round((fast_ma - slow_ma) / slow_ma * 100, 2)


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
    if (
        display_buy is not None
        and snapshot.ref_buy_price is not None
        and abs(display_buy - snapshot.ref_buy_price) >= INTRADAY_ANCHOR_MIN_DELTA
    ):
        adjusted = True
    if (
        display_sell is not None
        and snapshot.ref_sell_price is not None
        and abs(display_sell - snapshot.ref_sell_price) >= INTRADAY_ANCHOR_MIN_DELTA
    ):
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
        lines.append(
            f"相对300%（{SIGNAL_BENCHMARK_LOOKBACK}日）：{snapshot.relative_index_pct:+.2f}"
        )

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
    anchor_buy = (
        f"支撑锚点：日 K 慢线 MA{slow_window} 结构位，反映均线支撑/跌破水平，"
        "用于判断结构是否破坏，非直接买卖价。"
    )
    anchor_sell = (
        f"阻力锚点：日 K 快线 MA{fast_window} 与近高形成的结构阻力，"
        "用于观察反弹压力，非直接买卖价。"
    )
    if signal == "buy":
        ref_buy = (
            f"参考买价：买入信号下的动作参考，取 min(金叉价/慢{slow_window}/收盘/现价) 偏低吸；"
            "有实时行情时纳入现价。"
        )
        ref_sell = "参考卖价：买入信号下的止盈阻力参考，取近高与快线阻力区间的较低值。"
    elif signal == "sell":
        ref_buy = (
            "参考买价：卖出信号下的回补参考，取近 20 日低或现价下方，"
            "表示若反弹回落可关注的位置，非当前结构慢线。"
        )
        ref_sell = (
            f"参考卖价：卖出信号下的离场参考，有行情时取现价，"
            f"否则取 max(收盘/快{fast_window}) 反弹减仓位。"
        )
    elif signal == "hold":
        ref_buy = (
            f"参考买价：观望下的回踩关注位，取 min(慢{slow_window}/收盘/现价)。"
        )
        ref_sell = (
            f"参考卖价：观望下的反弹关注位，取 max(快{fast_window}/收盘/现价)。"
        )
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
        return text, _signal_sort_key(snapshot.signal)
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


def _signal_sort_key(signal: SignalKind) -> int:
    return {"buy": 3, "hold": 2, "sell": 1, "na": 0}[signal]


def signal_row_sort_key(snapshot: SignalSnapshot | None) -> tuple[int, float, str]:
    """信号区表格排序：信号优先级 > 强度 > 代码。"""
    if snapshot is None:
        return (0, float("-inf"), "")
    strength = snapshot.strength if snapshot.strength is not None else float("-inf")
    return (_signal_sort_key(snapshot.signal), strength, snapshot.vt_symbol)
