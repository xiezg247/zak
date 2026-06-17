"""极致短线信号：打板（日 K / 行情代理）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from vnpy_ashare.screener.hard_filters import is_at_limit_board, limit_board_threshold_pct

SignalKind = Literal["buy", "sell", "hold", "na"]


def calc_limit_price(prev_close: float, *, symbol: str) -> float:
    if prev_close <= 0:
        return 0.0
    threshold = 0.20 if symbol.startswith(("300", "688")) else 0.10
    return round(prev_close * (1 + threshold), 2)


def _bar_date_text(bar_dt: date | datetime) -> str:
    return bar_dt.strftime("%Y-%m-%d") if isinstance(bar_dt, datetime) else bar_dt.isoformat()


def _limit_up_bar(
    closes: list[float],
    highs: list[float],
    dates: list[date | datetime],
    index: int,
    *,
    symbol: str,
) -> bool:
    if index < 1:
        return False
    prev_close = closes[index - 1]
    if prev_close <= 0:
        return False
    change_pct = (closes[index] - prev_close) / prev_close * 100
    row = {
        "symbol": symbol,
        "change_pct": change_pct,
        "last_price": closes[index],
        "close": closes[index],
    }
    if not is_at_limit_board(row):
        return False
    return highs[index] > 0 and closes[index] >= highs[index] * 0.998


def classify_limit_board_signal(
    *,
    limit_up_today: bool,
    recent_days: int = 1,
    days_since_event: int | None,
) -> SignalKind:
    if limit_up_today:
        return "buy"
    if days_since_event is not None and days_since_event <= recent_days:
        return "hold"
    return "hold"


def build_limit_board_signal_payload(
    closes: list[float],
    dates: list[date | datetime],
    *,
    vt_symbol: str,
    strategy_id: str = "AshareLimitBoardStrategy",
    highs: list[float] | None = None,
    volumes: list[float] | None = None,
    recent_days: int = 1,
) -> dict[str, Any]:
    """打板信号快照（日 K 涨停 + 封板代理；完整分 K 规则 Phase 5）。"""
    symbol = vt_symbol.split(".", 1)[0]
    high_series = highs if highs is not None else closes
    warnings: list[str] = []
    if len(closes) < 3:
        return {
            "vt_symbol": vt_symbol,
            "strategy_id": strategy_id,
            "as_of": "",
            "signal": "na",
            "signal_label": "—",
            "signal_date": None,
            "ref_buy_price": None,
            "ref_sell_price": None,
            "action_ref_buy_price": None,
            "action_ref_sell_price": None,
            "strength": None,
            "reason_summary": "",
            "reasons": (),
            "warnings": ("K 线数量不足",),
            "last_close": None,
        }

    last_index = len(closes) - 1
    as_of = _bar_date_text(dates[last_index])
    last_close = round(closes[last_index], 2)
    prev_close = closes[last_index - 1]
    limit_price = calc_limit_price(prev_close, symbol=symbol)
    limit_up_today = _limit_up_bar(closes, high_series, dates, last_index, symbol=symbol)

    last_event_index: int | None = None
    for index in range(last_index, 0, -1):
        if _limit_up_bar(closes, high_series, dates, index, symbol=symbol):
            last_event_index = index
            break

    days_since: int | None = None
    signal_date: str | None = None
    if last_event_index is not None:
        signal_date = _bar_date_text(dates[last_event_index])
        end = dates[last_index]
        start = dates[last_event_index]
        end_d = end.date() if isinstance(end, datetime) else end
        start_d = start.date() if isinstance(start, datetime) else start
        days_since = (end_d - start_d).days

    signal = classify_limit_board_signal(
        limit_up_today=limit_up_today,
        recent_days=recent_days,
        days_since_event=days_since,
    )
    labels = {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}

    threshold = limit_board_threshold_pct({"symbol": symbol})
    change_pct = (last_close - prev_close) / prev_close * 100 if prev_close > 0 else 0.0

    reasons: list[str] = []
    if limit_up_today:
        reasons.append(f"涨停封板代理：涨幅 {change_pct:.1f}%（阈值 {threshold:.1f}%）")
        reasons.append(f"涨停价参考 {limit_price:.2f}")
    elif last_event_index is not None and days_since is not None and days_since <= recent_days:
        reasons.append(f"近 {recent_days} 日有涨停：{signal_date}")
    else:
        reasons.append("未触及涨停价/封板条件")

    warnings.append("日 K 代理规则，非分 K 打板；须结合情绪周期与龙头地位")

    strength = 85.0 if limit_up_today else 45.0 if days_since is not None and days_since <= recent_days else 30.0

    ref_buy = limit_price if limit_up_today or (days_since is not None and days_since <= recent_days) else None
    ref_sell = last_close if signal == "buy" else None
    action_buy = limit_price if limit_up_today else ref_buy
    action_sell = last_close

    return {
        "vt_symbol": vt_symbol,
        "strategy_id": strategy_id,
        "as_of": as_of,
        "signal": signal,
        "signal_label": labels[signal],
        "signal_date": signal_date if signal == "buy" else None,
        "ref_buy_price": ref_buy,
        "ref_sell_price": ref_sell,
        "action_ref_buy_price": action_buy,
        "action_ref_sell_price": action_sell,
        "strength": strength,
        "reason_summary": "涨停" if limit_up_today else "打板观望",
        "reasons": tuple(reasons),
        "warnings": tuple(warnings),
        "last_close": last_close,
        "limit_price": limit_price,
        "change_pct": round(change_pct, 2),
    }
