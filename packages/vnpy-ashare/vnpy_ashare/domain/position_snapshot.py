"""自选页持仓策略快照（投研记账 + 规则信号，非实盘持仓）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from vnpy_ashare.domain.market_hours import CHINA_TZ
from vnpy_ashare.domain.signal_snapshot import SignalKind, SignalSnapshot

PositionSource = Literal["manual", "gateway", "paper"]


@dataclass(frozen=True)
class PositionRecord:
    """zak.db 持仓行（投研记账）。"""

    symbol: str
    exchange: str
    name: str
    cost_price: float
    volume: int
    buy_date: str
    notes: str = ""
    source: PositionSource = "manual"

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"

    @property
    def position_key(self) -> str:
        return f"{self.cost_price}:{self.volume}:{self.buy_date}"


@dataclass(frozen=True)
class PositionSnapshot:
    vt_symbol: str
    name: str
    cost_price: float
    volume: int
    buy_date: str
    source: PositionSource
    last_price: float | None
    market_value: float | None
    unrealized_pnl: float | None
    unrealized_pnl_pct: float | None
    exit_signal: SignalKind
    signal_snapshot: SignalSnapshot | None
    t1_locked: bool
    exit_ref_price: float | None
    dist_exit_pct: float | None
    warnings: tuple[str, ...]

    @property
    def t1_status_label(self) -> str:
        return "T+1 锁定" if self.t1_locked else "可卖"

    @property
    def t1_status_tooltip(self) -> str:
        if self.t1_locked:
            return f"买入日 {self.buy_date[:10]}：当日买入不可卖（A 股 T+1）"
        return f"买入日 {self.buy_date[:10]}：已过 T+1，可按策略卖出"

    @property
    def exit_signal_label(self) -> str:
        labels = {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}
        return labels.get(self.exit_signal, "—")

    @property
    def exit_signal_tooltip(self) -> str:
        if self.signal_snapshot is not None and self.signal_snapshot.tooltip:
            return self.signal_snapshot.tooltip
        return f"策略退出信号：{self.exit_signal_label}"


def _parse_date(value: str | None) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def position_t1_locked(buy_date: str, *, trading_day: date | None = None) -> bool:
    """买入当日不可卖（A 股 T+1，记账辅助提示）。"""
    parsed = _parse_date(buy_date)
    if parsed is None:
        return False
    day = trading_day or datetime.now(CHINA_TZ).date()
    return parsed >= day


def compute_unrealized_pnl(
    cost_price: float,
    volume: int,
    last_price: float | None,
) -> tuple[float | None, float | None, float | None]:
    """返回 (市值, 浮盈, 浮盈%)。"""
    if last_price is None or last_price <= 0 or cost_price <= 0 or volume <= 0:
        return None, None, None
    market_value = round(last_price * volume, 2)
    cost_total = cost_price * volume
    pnl = round(market_value - cost_total, 2)
    pnl_pct = round((last_price - cost_price) / cost_price * 100, 2)
    return market_value, pnl, pnl_pct


def dist_exit_pct(ref_sell_price: float | None, last_price: float | None) -> float | None:
    if ref_sell_price is None or last_price is None or ref_sell_price <= 0:
        return None
    return round((last_price - ref_sell_price) / ref_sell_price * 100, 2)


def build_position_snapshot(
    record: PositionRecord,
    *,
    signal: SignalSnapshot | None,
    last_price: float | None,
    trading_day: date | None = None,
) -> PositionSnapshot:
    market_value, pnl, pnl_pct = compute_unrealized_pnl(record.cost_price, record.volume, last_price)
    exit_signal: SignalKind = signal.signal if signal is not None else "na"
    exit_ref = signal.ref_sell_price if signal is not None else None
    warnings = tuple(signal.warnings) if signal is not None and signal.warnings else ()
    locked = position_t1_locked(record.buy_date, trading_day=trading_day)
    return PositionSnapshot(
        vt_symbol=record.vt_symbol,
        name=record.name,
        cost_price=record.cost_price,
        volume=record.volume,
        buy_date=record.buy_date,
        source=record.source,
        last_price=last_price,
        market_value=market_value,
        unrealized_pnl=pnl,
        unrealized_pnl_pct=pnl_pct,
        exit_signal=exit_signal,
        signal_snapshot=signal,
        t1_locked=locked,
        exit_ref_price=exit_ref,
        dist_exit_pct=dist_exit_pct(exit_ref, last_price),
        warnings=warnings,
    )


def position_row_sort_key(snapshot: PositionSnapshot) -> tuple:
    """卖出信号优先，亏损靠前，再按代码。"""
    signal_rank = {"sell": 0, "hold": 1, "buy": 2, "na": 3}
    pnl_pct = snapshot.unrealized_pnl_pct if snapshot.unrealized_pnl_pct is not None else 0.0
    return (signal_rank.get(snapshot.exit_signal, 9), pnl_pct, snapshot.vt_symbol)
