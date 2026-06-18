"""隔日退出共享规则片段（日 K quote 与分 K 共用）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences.trading_risk import DEFAULT_STOP_LOSS_PCT, load_trading_risk_prefs
from vnpy_ashare.domain.trading.exit import ExitRuleHit, ExitSignal
from vnpy_ashare.domain.trading.position import position_t1_locked

T1_LOCKED_WARNING = ("T+1 锁定，当日不可卖",)


def resolve_stop_loss_pct(stop_loss_pct: float | None) -> float:
    prefs = load_trading_risk_prefs()
    stop_pct = stop_loss_pct if stop_loss_pct is not None else prefs.stop_loss_pct
    return stop_pct if stop_pct > 0 else DEFAULT_STOP_LOSS_PCT


def is_t1_locked(buy_date: str) -> bool:
    return position_t1_locked(buy_date)


def compute_pnl_pct(cost_price: float, last_price: float) -> float | None:
    if cost_price <= 0 or last_price <= 0:
        return None
    return round((last_price - cost_price) / cost_price * 100, 2)


def apply_stop_loss_pct_rule(
    rules: list[ExitRuleHit],
    reasons: list[str],
    *,
    pnl_pct: float | None,
    stop_pct: float,
    signal: ExitSignal,
) -> ExitSignal:
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
        return "sell"
    return signal


def apply_stop_loss_near_rule(
    rules: list[ExitRuleHit],
    warnings: list[str],
    *,
    pnl_pct: float | None,
    stop_pct: float,
    signal: ExitSignal,
) -> None:
    if signal == "hold" and pnl_pct is not None and pnl_pct <= -(stop_pct * 100 * 0.8):
        rules.append(
            ExitRuleHit(
                rule_id="stop_loss_near",
                label="逼近止损",
                status="near",
                detail=f"浮亏 {pnl_pct:.1f}%",
            )
        )
        warnings.append(f"接近 −{stop_pct * 100:.0f}% 止损线")


def append_limit_hold_rule(rules: list[ExitRuleHit]) -> None:
    rules.append(
        ExitRuleHit(
            rule_id="limit_hold",
            label="封板",
            status="clear",
            detail="涨停封板，隔日规则建议持有",
        )
    )


def append_limit_break_rule(
    rules: list[ExitRuleHit],
    reasons: list[str],
    *,
    detail: str,
    signal: ExitSignal,
) -> ExitSignal:
    rules.append(
        ExitRuleHit(
            rule_id="limit_break",
            label="炸板",
            status="triggered",
            detail=detail,
        )
    )
    if signal != "sell":
        reasons.append(detail)
    return "sell"
