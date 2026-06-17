"""自选页策略信号快照领域模型与纯规则（不含行情修饰）。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel

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
_SIGNAL_TRANSITION_TRACKED = frozenset({"buy", "sell", "hold"})


class SignalSnapshot(FrozenModel):
    vt_symbol: str = Field(description="VeighNa 合约代码")
    strategy_id: str = Field(description="策略标识")
    as_of: str = Field(description="信号计算截止交易日")
    signal: SignalKind = Field(description="信号类型：buy/sell/hold/na")
    signal_label: str = Field(description="信号展示文案")
    signal_date: str | None = Field(description="信号触发日 YYYY-MM-DD")
    ref_buy_price: float | None = Field(description="参考买入锚价")
    ref_sell_price: float | None = Field(description="参考卖出锚价")
    strength: float | None = Field(description="综合信号强度 0-100")
    reason_summary: str = Field(description="理由摘要")
    reasons: tuple[str, ...] = Field(description="详细理由列表")
    warnings: tuple[str, ...] = Field(description="警告信息列表")
    last_close: float | None = Field(default=None, description="最近收盘价")
    action_ref_buy_price: float | None = Field(default=None, description="动作买入锚价")
    action_ref_sell_price: float | None = Field(default=None, description="动作卖出锚价")
    fast_ma: float | None = Field(default=None, description="快线均线值")
    slow_ma: float | None = Field(default=None, description="慢线均线值")
    volume_ratio_5d: float | None = Field(default=None, description="5 日量比")
    ma_gap_pct: float | None = Field(default=None, description="快慢均线间距（%）")
    strength_cross: float | None = Field(default=None, description="交叉强度分项")
    strength_alignment: float | None = Field(default=None, description="均线排列强度分项")
    strength_volume: float | None = Field(default=None, description="量能强度分项")
    strength_pattern: float | None = Field(default=None, description="形态强度分项")
    relative_index_pct: float | None = Field(default=None, description="相对基准指数超额（%）")

    @property
    def tooltip(self) -> str:
        parts = list(self.reasons)
        if self.warnings:
            parts.extend(self.warnings)
        return "\n".join(part for part in parts if part)


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


def signal_snapshot_to_dict(snapshot: SignalSnapshot) -> dict[str, Any]:
    """序列化信号快照（供 AI 工具 JSON 返回）。"""
    return snapshot.model_dump(
        mode="json",
        exclude={"reasons"},
    )


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


def ma_gap_pct(fast_ma: float | None, slow_ma: float | None) -> float | None:
    """快慢均线间距占慢线比例（%）。"""
    if fast_ma is None or slow_ma is None or slow_ma <= 0:
        return None
    return round((fast_ma - slow_ma) / slow_ma * 100, 2)


def signal_sort_key(signal: SignalKind) -> int:
    return {"buy": 3, "hold": 2, "sell": 1, "na": 0}[signal]


def signal_row_sort_key(snapshot: SignalSnapshot | None) -> tuple[int, float, str]:
    """信号区表格排序：信号优先级 > 强度 > 代码。"""
    if snapshot is None:
        return (0, float("-inf"), "")
    strength = snapshot.strength if snapshot.strength is not None else float("-inf")
    return (signal_sort_key(snapshot.signal), strength, snapshot.vt_symbol)
