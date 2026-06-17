"""持仓异动判定（自选页持仓面板）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.quotes.market.market_breadth import LIMIT_UP_PCT
from vnpy_ashare.trading.exit.opening_stop import detect_opening_stop_loss
from vnpy_ashare.trading.journal.float_loss_hold import is_float_loss_hold

if TYPE_CHECKING:
    from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
    from vnpy_ashare.domain.trading.position import PositionSnapshot

INTRADAY_DROP_PCT = -3.0
INTRADAY_SURGE_PCT = 5.0
VOLUME_RATIO_ACTIVE = 1.2
FLOAT_LOSS_PCT = -5.0
FLOAT_GAIN_PCT = 15.0

_ANOMALY_WEIGHTS: dict[str, int] = {
    "卖出信号": 100,
    "开盘止损": 95,
    "急跌": 80,
    "浮亏": 60,
    "浮亏扛单": 58,
    "放量": 40,
    "大涨": 30,
    "浮盈": 20,
}


def position_anomaly_reasons(
    *,
    snap: PositionSnapshot | None,
    quote: QuoteSnapshot | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snap is not None and snap.exit_signal == "sell":
        reasons.append("卖出信号")

    if quote is not None and quote.last_price > 0:
        opening_hit, _detail = detect_opening_stop_loss(quote)
        if opening_hit:
            reasons.append("开盘止损")
        change_pct = float(quote.change_pct or 0)
        volume_ratio = float(quote.volume_ratio or 0)
        if change_pct <= INTRADAY_DROP_PCT:
            reasons.append("急跌")
        elif change_pct >= max(INTRADAY_SURGE_PCT, LIMIT_UP_PCT - 1.0):
            reasons.append("大涨")
        if volume_ratio >= VOLUME_RATIO_ACTIVE and abs(change_pct) >= 1.5:
            reasons.append("放量")

    if snap is not None and snap.unrealized_pnl_pct is not None:
        pnl_pct = float(snap.unrealized_pnl_pct)
        if is_float_loss_hold(snap):
            reasons.append("浮亏扛单")
        elif pnl_pct <= FLOAT_LOSS_PCT:
            reasons.append("浮亏")
        elif pnl_pct >= FLOAT_GAIN_PCT:
            reasons.append("浮盈")

    return tuple(reasons)


def is_position_anomaly(
    *,
    snap: PositionSnapshot | None,
    quote: QuoteSnapshot | None,
) -> bool:
    return bool(position_anomaly_reasons(snap=snap, quote=quote))


def position_anomaly_score(reasons: tuple[str, ...]) -> float:
    if not reasons:
        return 0.0
    return float(sum(_ANOMALY_WEIGHTS.get(reason, 10) for reason in reasons))


def format_anomaly_tags(reasons: tuple[str, ...]) -> str:
    if not reasons:
        return ""
    return " · ".join(reasons)
