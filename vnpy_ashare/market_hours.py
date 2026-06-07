"""A 股交易时段判断。"""

from __future__ import annotations

from datetime import datetime, time

from vnpy.trader.utility import ZoneInfo

CHINA_TZ = ZoneInfo("Asia/Shanghai")

MORNING_OPEN = time(9, 30)
MORNING_CLOSE = time(11, 30)
AFTERNOON_OPEN = time(13, 0)
AFTERNOON_CLOSE = time(15, 0)

INTRADAY_CHART_TAB = 0
DAILY_CHART_TAB = 1


def _to_china_time(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=CHINA_TZ)
    return dt.astimezone(CHINA_TZ)


def is_ashare_trading_session(dt: datetime | None = None) -> bool:
    """工作日 9:30–11:30、13:00–15:00（不含节假日）。"""
    now = _to_china_time(dt or datetime.now(CHINA_TZ))
    if now.weekday() >= 5:
        return False
    current = now.time()
    if MORNING_OPEN <= current <= MORNING_CLOSE:
        return True
    if AFTERNOON_OPEN <= current <= AFTERNOON_CLOSE:
        return True
    return False


def default_chart_tab_index(dt: datetime | None = None) -> int:
    """交易时段默认分时，其余默认日 K。"""
    return INTRADAY_CHART_TAB if is_ashare_trading_session(dt) else DAILY_CHART_TAB
