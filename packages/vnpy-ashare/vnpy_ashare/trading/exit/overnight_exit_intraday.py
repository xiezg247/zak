"""隔日退出分 K 评估（开盘止损 + 止损线 + 炸板）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from strategies.ultra_short_signals import calc_limit_price
from vnpy_ashare.domain.trading.exit import ExitRuleHit, ExitSignal
from vnpy_ashare.domain.trading.position import PositionRecord
from vnpy_ashare.screener.hard_filters import is_at_limit_board
from vnpy_ashare.trading.exit.opening_stop import OPENING_STOP_MINUTES
from vnpy_ashare.trading.exit.opening_stop_intraday import detect_opening_stop_from_minute_bars
from vnpy_ashare.trading.exit.overnight_exit_rules import (
    T1_LOCKED_WARNING,
    append_limit_break_rule,
    append_limit_hold_rule,
    apply_stop_loss_near_rule,
    apply_stop_loss_pct_rule,
    compute_pnl_pct,
    is_t1_locked,
    resolve_stop_loss_pct,
)
from vnpy_ashare.trading.signals.limit_board_intraday import load_local_minute_bars_for_date
from vnpy_ashare.trading.signals.pullback_intraday import resolve_daily_mas_for_date
from vnpy_ashare.trading.signals.seal_reopen import detect_seal_reopen_from_minute_bars

SessionPhase = Literal["partial", "closed"]


@dataclass(frozen=True)
class OvernightExitIntradaySnapshot:
    signal: ExitSignal
    ref_sell_price: float | None
    rules: tuple[ExitRuleHit, ...]
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


class _MinuteBarLike:
    datetime: object
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float


def evaluate_overnight_exit_intraday(
    bars: list[_MinuteBarLike],
    record: PositionRecord,
    *,
    prev_close: float,
    stop_loss_pct: float | None = None,
    stop_minutes: int = OPENING_STOP_MINUTES,
    phase: SessionPhase = "partial",
) -> OvernightExitIntradaySnapshot:
    """分 K 隔日退出评估（T+1 可卖日）。"""
    if is_t1_locked(record.buy_date):
        return OvernightExitIntradaySnapshot(
            signal="hold",
            ref_sell_price=None,
            rules=(),
            reasons=(),
            warnings=T1_LOCKED_WARNING,
        )

    stop_pct = resolve_stop_loss_pct(stop_loss_pct)

    if not bars:
        return OvernightExitIntradaySnapshot(
            signal="hold",
            ref_sell_price=None,
            rules=(),
            reasons=(),
            warnings=("无有效分 K",),
        )

    last_close = float(bars[-1].close_price)
    ref_sell = last_close
    rules: list[ExitRuleHit] = []
    reasons: list[str] = []
    warnings: list[str] = []
    signal: ExitSignal = "hold"

    pnl_pct = compute_pnl_pct(record.cost_price, last_close)

    signal = apply_stop_loss_pct_rule(
        rules,
        reasons,
        pnl_pct=pnl_pct,
        stop_pct=stop_pct,
        signal=signal,
    )

    if prev_close > 0:
        opening_hit, opening_detail = detect_opening_stop_from_minute_bars(
            bars,
            prev_close=prev_close,
            stop_minutes=stop_minutes,
            phase=phase,
        )
        if opening_hit:
            rules.append(
                ExitRuleHit(
                    rule_id="opening_30min_stop",
                    label="开盘止损",
                    status="triggered",
                    detail=opening_detail,
                )
            )
            reasons.append(opening_detail)
            signal = "sell"

        symbol = record.symbol
        limit_price = calc_limit_price(prev_close, symbol=symbol)
        reopen_kind, _ = detect_seal_reopen_from_minute_bars(bars, limit_price=limit_price)
        row = {"symbol": symbol, "change_pct": (last_close - prev_close) / prev_close * 100 if prev_close else 0}
        if is_at_limit_board(row) and reopen_kind == "broken":
            signal = append_limit_break_rule(
                rules,
                reasons,
                detail="涨停打开且未能回封（分 K）",
                signal=signal,
            )
        elif is_at_limit_board(row) and reopen_kind in {"solid", "resealed"}:
            append_limit_hold_rule(rules)

    apply_stop_loss_near_rule(
        rules,
        warnings,
        pnl_pct=pnl_pct,
        stop_pct=stop_pct,
        signal=signal,
    )

    if phase == "partial" and signal == "hold":
        warnings.append("分 K 盘中评估（隔日退出）")

    return OvernightExitIntradaySnapshot(
        signal=signal,
        ref_sell_price=ref_sell,
        rules=tuple(rules),
        warnings=tuple(warnings),
        reasons=tuple(reasons),
    )


def evaluate_overnight_exit_from_local_minutes(
    record: PositionRecord,
    trade_date: date,
    *,
    stop_loss_pct: float | None = None,
) -> OvernightExitIntradaySnapshot | None:
    bars = load_local_minute_bars_for_date(record.vt_symbol, trade_date)
    if not bars:
        return None
    _, _, prev_close = resolve_daily_mas_for_date(record.vt_symbol, trade_date)
    if prev_close <= 0:
        return None
    return evaluate_overnight_exit_intraday(
        bars,
        record,
        prev_close=prev_close,
        stop_loss_pct=stop_loss_pct,
        phase="closed",
    )
