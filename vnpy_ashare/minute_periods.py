"""分 K 周期与本地存储键映射（仅 1 分 K）。"""

from __future__ import annotations

from datetime import timedelta

from vnpy.trader.constant import Interval

MINUTE_PERIOD = "1m"
MINUTE_PERIODS: tuple[str, ...] = (MINUTE_PERIOD,)

LOCAL_SCOPE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("日K", "daily"),
    ("1分", MINUTE_PERIOD),
)

PERIOD_LABELS: dict[str, str] = {MINUTE_PERIOD: "1分"}

DEFAULT_MINUTE_DOWNLOAD_MONTHS = 6
MAX_BARS_PER_REQUEST = 10000


def normalize_period(period: str) -> str:
    text = period.strip().lower()
    if text != MINUTE_PERIOD:
        raise ValueError(f"不支持的分 K 周期: {period}，仅支持 {MINUTE_PERIOD}")
    return text


def storage_interval(period: str) -> str:
    normalize_period(period)
    return Interval.MINUTE.value


def bar_interval(period: str) -> Interval:
    normalize_period(period)
    return Interval.MINUTE


def is_daily_scope(scope: str) -> bool:
    return scope == "daily"


def scope_display(scope: str) -> str:
    if is_daily_scope(scope):
        return "日K"
    return PERIOD_LABELS.get(scope, scope)


def period_step(period: str) -> timedelta:
    normalize_period(period)
    return timedelta(minutes=1)
