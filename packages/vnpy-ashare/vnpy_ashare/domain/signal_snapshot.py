"""自选页策略信号快照（规则计算，非买卖建议）。"""

from __future__ import annotations

from dataclasses import dataclass
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

SIGNAL_DISCLAIMER = "策略信号来自历史规则计算，仅供研究参考，不构成买卖建议。"


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

    @property
    def tooltip(self) -> str:
        parts = list(self.reasons)
        if self.warnings:
            parts.extend(self.warnings)
        parts.append(SIGNAL_DISCLAIMER)
        return "\n".join(part for part in parts if part)


def dist_buy_pct(ref_buy_price: float | None, last_price: float | None) -> float | None:
    if ref_buy_price is None or last_price is None or ref_buy_price <= 0:
        return None
    return round((last_price - ref_buy_price) / ref_buy_price * 100, 2)


def signal_cell_text(
    column_key: str,
    snapshot: SignalSnapshot | None,
    *,
    quote: QuoteSnapshot | None = None,
) -> tuple[str, float | str]:
    if snapshot is None:
        return "—", float("-inf")

    if column_key == "signal":
        return snapshot.signal_label, _signal_sort_key(snapshot.signal)
    if column_key == "signal_date":
        text = snapshot.signal_date or "—"
        return text, text
    if column_key == "ref_buy_price":
        if snapshot.ref_buy_price is None:
            return "—", float("-inf")
        return f"{snapshot.ref_buy_price:.2f}", snapshot.ref_buy_price
    if column_key == "ref_sell_price":
        if snapshot.ref_sell_price is None:
            return "—", float("-inf")
        return f"{snapshot.ref_sell_price:.2f}", snapshot.ref_sell_price
    if column_key == "dist_buy_pct":
        pct = dist_buy_pct(snapshot.ref_buy_price, quote.last_price if quote else None)
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


def signal_cell_color(column_key: str, snapshot: SignalSnapshot | None, *, colors) -> str | None:
    if column_key != "signal" or snapshot is None:
        return None
    if snapshot.signal == "buy":
        return colors.rise
    if snapshot.signal == "sell":
        return colors.fall
    return None


def _signal_sort_key(signal: SignalKind) -> int:
    return {"buy": 3, "hold": 2, "sell": 1, "na": 0}[signal]
