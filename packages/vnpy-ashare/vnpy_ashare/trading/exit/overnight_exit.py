"""隔日退出规则集（SP-05 · 非独立 CTA，绑定持仓区）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.domain.trading.exit import ExitRuleHit, ExitSignal, OvernightExitEvaluation, RuleStatus
from vnpy_ashare.domain.trading.position import PositionRecord
from vnpy_ashare.screener.hard_filters import is_at_limit_board
from vnpy_ashare.trading.exit.opening_stop_intraday import resolve_opening_stop_for_quote
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

if TYPE_CHECKING:
    from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot

__all__ = [
    "ExitRuleHit",
    "ExitSignal",
    "OvernightExitEvaluation",
    "RuleStatus",
    "evaluate_overnight_exit",
]


def _quote_row(quote: QuoteSnapshot | None, *, vt_symbol: str) -> dict[str, object]:
    if quote is None:
        return {"vt_symbol": vt_symbol}
    return {
        "vt_symbol": vt_symbol,
        "symbol": quote.symbol,
        "change_pct": quote.change_pct,
        "last_price": quote.last_price,
        "prev_close": quote.prev_close,
        "open_price": quote.open_price,
        "high_price": quote.high_price,
        "low_price": quote.low_price,
        "volume_ratio": quote.volume_ratio,
    }


def evaluate_overnight_exit(
    record: PositionRecord,
    *,
    quote: QuoteSnapshot | None = None,
    stop_loss_pct: float | None = None,
) -> OvernightExitEvaluation:
    """评估隔日退出规则（MVP：日 K + 实时行情字段）。"""
    if is_t1_locked(record.buy_date):
        return OvernightExitEvaluation(
            signal="hold",
            ref_sell_price=None,
            rules=(),
            warnings=T1_LOCKED_WARNING,
            reasons=(),
        )

    stop_pct = resolve_stop_loss_pct(stop_loss_pct)

    last = quote.last_price if quote is not None and quote.last_price > 0 else None
    prev_close = quote.prev_close if quote is not None and quote.prev_close > 0 else None
    open_price = quote.open_price if quote is not None and quote.open_price > 0 else None
    pnl_pct = compute_pnl_pct(record.cost_price, last) if last is not None else None

    rules: list[ExitRuleHit] = []
    reasons: list[str] = []
    warnings: list[str] = []
    signal: ExitSignal = "hold"
    ref_sell = last

    signal = apply_stop_loss_pct_rule(
        rules,
        reasons,
        pnl_pct=pnl_pct,
        stop_pct=stop_pct,
        signal=signal,
    )

    if quote is not None and prev_close is not None and open_price is not None and last is not None:
        opening_hit, opening_detail = resolve_opening_stop_for_quote(record.vt_symbol, quote, phase="partial")
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

        gap_pct = (open_price - prev_close) / prev_close * 100
        if not opening_hit and gap_pct < -0.5 and last < open_price and last < prev_close:
            rules.append(
                ExitRuleHit(
                    rule_id="gap_down_weak",
                    label="低开走弱",
                    status="triggered",
                    detail=f"低开 {gap_pct:.1f}%，现价低于开盘/昨收",
                )
            )
            if signal != "sell":
                reasons.append(rules[-1].detail)
            signal = "sell"

        if gap_pct >= 3.0 and gap_pct <= 5.0 and quote.volume_ratio < 1.0 and last < quote.high_price * 0.995:
            rules.append(
                ExitRuleHit(
                    rule_id="take_profit_weak_volume",
                    label="冲高量能不足",
                    status="near",
                    detail=f"开盘冲高 {gap_pct:.1f}%，量比 {quote.volume_ratio:.1f}",
                )
            )
            warnings.append("冲高 3–5% 但量能不足，考虑分批止盈")

        row = _quote_row(quote, vt_symbol=record.vt_symbol)
        if is_at_limit_board(row) and last is not None and last < quote.high_price * 0.995:
            signal = append_limit_break_rule(
                rules,
                reasons,
                detail="涨停打开且未能回封",
                signal=signal,
            )
        elif is_at_limit_board(row):
            append_limit_hold_rule(rules)

    apply_stop_loss_near_rule(
        rules,
        warnings,
        pnl_pct=pnl_pct,
        stop_pct=stop_pct,
        signal=signal,
    )

    return OvernightExitEvaluation(
        signal=signal,
        ref_sell_price=ref_sell,
        rules=tuple(rules),
        warnings=tuple(warnings),
        reasons=tuple(reasons),
    )
