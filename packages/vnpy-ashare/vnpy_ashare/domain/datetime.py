"""东八区时间工具（统一 CHINA_TZ，避免各模块自建 ZoneInfo）。"""

from __future__ import annotations

from datetime import date, datetime

from vnpy_ashare.domain.market_hours import CHINA_TZ

DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
DATETIME_MINUTE_FMT = "%Y-%m-%d %H:%M"
TIME_HM_FMT = "%H:%M"
DATE_FMT = "%Y-%m-%d"


def china_now() -> datetime:
    return datetime.now(CHINA_TZ)


def china_today() -> date:
    return china_now().date()


def format_china_datetime(dt: datetime | None = None) -> str:
    return _format_china(dt, DATETIME_FMT)


def format_china_datetime_minute(dt: datetime | None = None) -> str:
    return _format_china(dt, DATETIME_MINUTE_FMT)


def format_china_time_hm(dt: datetime | None = None) -> str:
    return _format_china(dt, TIME_HM_FMT)


def format_china_date(dt: datetime | None = None) -> str:
    return _format_china(dt, DATE_FMT)


def _format_china(dt: datetime | None, fmt: str) -> str:
    value = dt or china_now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=CHINA_TZ)
    else:
        value = value.astimezone(CHINA_TZ)
    return value.strftime(fmt)
