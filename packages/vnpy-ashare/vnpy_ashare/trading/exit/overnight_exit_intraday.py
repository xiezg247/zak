"""隔日退出分 K 评估（开盘止损 + 止损线 + 炸板）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from strategies.ultra_short_signals import calc_limit_price
from vnpy_ashare.config.preferences.trading_risk import DEFAULT_STOP_LOSS_PCT, load_trading_risk_prefs
from vnpy_ashare.domain.trading.exit import ExitRuleHit, ExitSignal
from vnpy_ashare.domain.trading.position import PositionRecord, position_t1_locked
from vnpy_ashare.screener.hard_filters import is_at_limit_board
from vnpy_ashare.trading.exit.opening_stop import OPENING_STOP_MINUTES
from vnpy_ashare.trading.exit.opening_stop_intraday import detect_opening_stop_from_minute_bars
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
    if position_t1_locked(record.buy_date):
        return OvernightExitIntradaySnapshot(
            signal="hold",
            ref_sell_price=None,
            rules=(),
            reasons=(),
            warnings=("T+1 锁定，当日不可卖",),
        )

    prefs = load_trading_risk_prefs()
    stop_pct = stop_loss_pct if stop_loss_pct is not None else prefs.stop_loss_pct
    stop_pct = stop_pct if stop_pct > 0 else DEFAULT_STOP_LOSS_PCT

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

    pnl_pct: float | None = None
    if record.cost_price > 0:
        pnl_pct = round((last_close - record.cost_price) / record.cost_price * 100, 2)

    if pnl_pct is not None and pnl_pct <= -stop_pct * 100:
        rules.append(
            ExitRuleHit(
                rule_id="stop_loss_pct",
                label="止损",
                status="triggered",
                detail=f"浮亏 {pnl_pct:.1f}% ≤ −{stop_pct * 100:.0f}%",
            )
        )
        reasons.append(rules[-1].detail)
        signal = "sell"

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
            rules.append(
                ExitRuleHit(
                    rule_id="limit_break",
                    label="炸板",
                    status="triggered",
                    detail="涨停打开且未能回封（分 K）",
                )
            )
            if signal != "sell":
                reasons.append(rules[-1].detail)
            signal = "sell"
        elif is_at_limit_board(row) and reopen_kind in {"solid", "resealed"}:
            rules.append(
                ExitRuleHit(
                    rule_id="limit_hold",
                    label="封板",
                    status="clear",
                    detail="涨停封板，隔日规则建议持有",
                )
            )

    if signal == "hold" and pnl_pct is not None and pnl_pct <= -(stop_pct * 100 * 0.8):
        rules.append(
            ExitRuleHit(
                rule_id="stop_loss_near",
                label="逼近止损",
                status="near",
                detail=f"浮盈 {pnl_pct:.1f}%",
            )
        )
        warnings.append(f"接近 −{stop_pct * 100:.0f}% 止损线")

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
