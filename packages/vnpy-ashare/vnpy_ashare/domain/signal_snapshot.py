"""自选页策略信号快照（规则计算，非买卖建议）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

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
INTRADAY_ANCHOR_MIN_DELTA = 0.01

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

    @property
    def tooltip(self) -> str:
        parts = list(self.reasons)
        if self.warnings:
            parts.extend(self.warnings)
        return "\n".join(part for part in parts if part)


def dist_buy_pct(ref_buy_price: float | None, last_price: float | None) -> float | None:
    if ref_buy_price is None or last_price is None or ref_buy_price <= 0:
        return None
    return round((last_price - ref_buy_price) / ref_buy_price * 100, 2)


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
    return (anchor_buy, anchor_sell, ref_buy, ref_sell, dist)


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

    return tuple(hints)


def signal_cell_text(
    column_key: str,
    snapshot: SignalSnapshot | None,
    *,
    quote: QuoteSnapshot | None = None,
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
        return snapshot.signal_label, _signal_sort_key(snapshot.signal)
    if column_key == "signal_date":
        text = snapshot.signal_date or "—"
        return text, text
    if column_key == "anchor_buy":
        if snapshot.ref_buy_price is None:
            return "—", float("-inf")
        return f"{snapshot.ref_buy_price:.2f}", snapshot.ref_buy_price
    if column_key == "anchor_sell":
        if snapshot.ref_sell_price is None:
            return "—", float("-inf")
        return f"{snapshot.ref_sell_price:.2f}", snapshot.ref_sell_price
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
    warning_color: str | None = None,
    slow_window: int = 20,
    fast_window: int = 10,
) -> str | None:
    if snapshot is None:
        return None
    if column_key == "signal":
        if snapshot.signal == "buy":
            return colors.rise
        if snapshot.signal == "sell":
            return colors.fall
        return None
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
    return None


def _signal_sort_key(signal: SignalKind) -> int:
    return {"buy": 3, "hold": 2, "sell": 1, "na": 0}[signal]


def signal_row_sort_key(snapshot: SignalSnapshot | None) -> tuple[int, float, str]:
    """信号区表格排序：信号优先级 > 强度 > 代码。"""
    if snapshot is None:
        return (0, float("-inf"), "")
    strength = snapshot.strength if snapshot.strength is not None else float("-inf")
    return (_signal_sort_key(snapshot.signal), strength, snapshot.vt_symbol)
