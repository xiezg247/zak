"""分 K 开盘 30 分钟止损检测。"""

from __future__ import annotations

from datetime import datetime, time

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.time.market_hours import CHINA_TZ, MORNING_OPEN
from vnpy_ashare.trading.exit.opening_stop import OPENING_STOP_MINUTES, detect_opening_stop_loss
from vnpy_ashare.trading.signals.limit_board_intraday import load_local_minute_bars_for_date

__all__ = [
    "detect_opening_stop_from_minute_bars",
    "never_recovered_prev_close_in_opening_window",
    "resolve_opening_stop_for_quote",
]


class _MinuteBarLike:
    datetime: datetime
    open_price: float
    high_price: float
    close_price: float


def _bar_clock_minutes(bar: _MinuteBarLike) -> int | None:
    local = bar.datetime
    if local.tzinfo is None:
        local = local.replace(tzinfo=CHINA_TZ)
    else:
        local = local.astimezone(CHINA_TZ)
    return local.hour * 60 + local.minute


def _session_bars(bars: list[_MinuteBarLike]) -> list[_MinuteBarLike]:
    ordered = sorted(bars, key=lambda item: item.datetime)
    result: list[_MinuteBarLike] = []
    for bar in ordered:
        local = bar.datetime
        if local.tzinfo is None:
            local = local.replace(tzinfo=CHINA_TZ)
        else:
            local = local.astimezone(CHINA_TZ)
        if time(9, 30) <= local.time() <= time(15, 0):
            result.append(bar)
    return result


def _opening_window_bars(
    bars: list[_MinuteBarLike],
    *,
    stop_minutes: int = OPENING_STOP_MINUTES,
) -> list[_MinuteBarLike]:
    start_min = MORNING_OPEN.hour * 60 + MORNING_OPEN.minute
    end_min = start_min + max(1, int(stop_minutes))
    result: list[_MinuteBarLike] = []
    for bar in bars:
        minutes = _bar_clock_minutes(bar)
        if minutes is None:
            continue
        if start_min <= minutes < end_min:
            result.append(bar)
    return result


def never_recovered_prev_close_in_opening_window(
    bars: list[_MinuteBarLike],
    *,
    prev_close: float,
    open_price: float | None = None,
    stop_minutes: int = OPENING_STOP_MINUTES,
    tolerance: float = 0.001,
) -> bool:
    """开盘窗口内是否从未触及昨收（翻红）。"""
    if prev_close <= 0:
        return False
    session = _session_bars(bars)
    if not session:
        return False
    day_open = open_price if open_price is not None and open_price > 0 else float(session[0].open_price)
    if day_open >= prev_close:
        return False
    threshold = prev_close * (1 - tolerance)
    window = _opening_window_bars(session, stop_minutes=stop_minutes)
    if not window:
        return False
    return all(float(bar.high_price) < threshold for bar in window)


def detect_opening_stop_from_minute_bars(
    bars: list[_MinuteBarLike],
    *,
    prev_close: float,
    open_price: float | None = None,
    stop_minutes: int = OPENING_STOP_MINUTES,
    phase: str = "partial",
) -> tuple[bool, str]:
    """分 K 版开盘止损：低开 + 开盘窗口内未翻红。"""
    if prev_close <= 0:
        return False, ""
    session = _session_bars(bars)
    if not session:
        return False, ""
    day_open = open_price if open_price is not None and open_price > 0 else float(session[0].open_price)
    if day_open >= prev_close:
        return False, ""

    window = _opening_window_bars(session, stop_minutes=stop_minutes)
    if not window:
        return False, ""

    last = window[-1]
    last_close = float(last.close_price)
    if last_close >= prev_close:
        return False, ""

    if phase == "partial":
        last_minutes = _bar_clock_minutes(last)
        start_min = MORNING_OPEN.hour * 60 + MORNING_OPEN.minute
        end_min = start_min + stop_minutes
        if last_minutes is not None and last_minutes >= end_min:
            phase = "closed"

    if not never_recovered_prev_close_in_opening_window(
        session,
        prev_close=prev_close,
        open_price=day_open,
        stop_minutes=stop_minutes,
    ):
        return False, ""

    gap_pct = (day_open - prev_close) / prev_close * 100
    return True, f"低开 {gap_pct:.1f}%，30 分钟内未翻红（分 K）"


def resolve_opening_stop_for_quote(
    vt_symbol: str,
    quote: QuoteSnapshot,
    *,
    phase: str = "partial",
) -> tuple[bool, str]:
    """优先本地 1m 分 K 检测开盘止损，无数据时回退日 K 代理。"""
    if quote.last_price <= 0 or quote.prev_close <= 0 or quote.open_price <= 0:
        return False, ""
    trade_date = datetime.now(CHINA_TZ).date()
    minute_bars = load_local_minute_bars_for_date(vt_symbol, trade_date)
    if minute_bars:
        hit, detail = detect_opening_stop_from_minute_bars(
            minute_bars,
            prev_close=quote.prev_close,
            open_price=quote.open_price,
            phase=phase,
        )
        if hit:
            return hit, detail
    return detect_opening_stop_loss(quote)
