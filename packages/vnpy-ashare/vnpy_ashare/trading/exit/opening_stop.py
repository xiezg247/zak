"""开盘 30 分钟止损检测（S-05）。"""

from __future__ import annotations

from datetime import datetime, time

from vnpy_ashare.domain.time.market_hours import CHINA_TZ, MORNING_OPEN
from vnpy_ashare.domain.time.quote_time import normalize_datetime_text
from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot

OPENING_STOP_MINUTES = 30


def _parse_time_of_day(trade_time: str) -> time | None:
    text = normalize_datetime_text(trade_time)
    if not text:
        return None
    if " " in text:
        text = text.split(" ", 1)[1]
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            parsed = datetime.strptime(text[: len(fmt)], fmt)
            return parsed.time()
        except ValueError:
            continue
    return None


def is_within_opening_minutes(
    trade_time: str = "",
    *,
    minutes: int = OPENING_STOP_MINUTES,
    now: datetime | None = None,
) -> bool:
    """是否处于早盘开盘后的 N 分钟内（默认 30 分钟）。"""
    clock = _parse_time_of_day(trade_time)
    if clock is None:
        probe = now or datetime.now(CHINA_TZ)
        if probe.tzinfo is None:
            probe = probe.replace(tzinfo=CHINA_TZ)
        else:
            probe = probe.astimezone(CHINA_TZ)
        clock = probe.time()
    start = MORNING_OPEN
    start_min = start.hour * 60 + start.minute
    current_min = clock.hour * 60 + clock.minute
    end_min = start_min + max(1, int(minutes))
    return start_min <= current_min < end_min


def detect_opening_stop_loss(quote: QuoteSnapshot | None) -> tuple[bool, str]:
    """低开且开盘 30 分钟内仍未翻红（现价 < 昨收）。"""
    if quote is None or quote.last_price <= 0 or quote.prev_close <= 0 or quote.open_price <= 0:
        return False, ""
    if quote.open_price >= quote.prev_close:
        return False, ""
    if quote.last_price >= quote.prev_close:
        return False, ""
    if not is_within_opening_minutes(quote.trade_time):
        return False, ""
    gap_pct = (quote.open_price - quote.prev_close) / quote.prev_close * 100
    return True, f"低开 {gap_pct:.1f}%，30 分钟内未翻红"
