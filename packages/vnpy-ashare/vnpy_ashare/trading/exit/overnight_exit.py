"""隔日退出规则集（SP-05 · 非独立 CTA，绑定持仓区）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.config.preferences.trading_risk import DEFAULT_STOP_LOSS_PCT, load_trading_risk_prefs
from vnpy_ashare.domain.trading.exit import ExitRuleHit, ExitSignal, OvernightExitEvaluation, RuleStatus
from vnpy_ashare.domain.trading.position import PositionRecord, position_t1_locked
from vnpy_ashare.screener.hard_filters import is_at_limit_board
from vnpy_ashare.trading.exit.opening_stop import detect_opening_stop_loss

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
    if position_t1_locked(record.buy_date):
        return OvernightExitEvaluation(
            signal="hold",
            ref_sell_price=None,
            rules=(),
            warnings=("T+1 锁定，当日不可卖",),
            reasons=(),
        )

    prefs = load_trading_risk_prefs()
    stop_pct = stop_loss_pct if stop_loss_pct is not None else prefs.stop_loss_pct
    stop_pct = stop_pct if stop_pct > 0 else DEFAULT_STOP_LOSS_PCT

    last = quote.last_price if quote is not None and quote.last_price > 0 else None
    prev_close = quote.prev_close if quote is not None and quote.prev_close > 0 else None
    open_price = quote.open_price if quote is not None and quote.open_price > 0 else None
    pnl_pct: float | None = None
    if last is not None and record.cost_price > 0:
        pnl_pct = round((last - record.cost_price) / record.cost_price * 100, 2)

    rules: list[ExitRuleHit] = []
    reasons: list[str] = []
    warnings: list[str] = []
    signal: ExitSignal = "hold"
    ref_sell = last

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

    if quote is not None and prev_close is not None and open_price is not None and last is not None:
        opening_hit, opening_detail = detect_opening_stop_loss(quote)
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
            rules.append(
                ExitRuleHit(
                    rule_id="limit_break",
                    label="炸板",
                    status="triggered",
                    detail="涨停打开且未能回封",
                )
            )
            if signal != "sell":
                reasons.append(rules[-1].detail)
            signal = "sell"
        elif is_at_limit_board(row):
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

    return OvernightExitEvaluation(
        signal=signal,
        ref_sell_price=ref_sell,
        rules=tuple(rules),
        warnings=tuple(warnings),
        reasons=tuple(reasons),
    )
