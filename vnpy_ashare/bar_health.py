"""本地日 K 覆盖与健康状态。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from vnpy_ashare.calendar import last_trading_day, trading_days_between


class BarHealthStatus(str, Enum):
    OK = "ok"
    STALE = "stale"
    GAPS = "gaps"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BarMeta:
    start: datetime
    end: datetime
    count: int


@dataclass(frozen=True)
class GapRange:
    start: date
    end: date
    missing_days: int


@dataclass(frozen=True)
class BarGapResult:
    status: BarHealthStatus
    gaps: list[GapRange]
    expected_days: int
    actual_days: int


def list_status(meta: BarMeta | None, *, as_of: date | None = None) -> BarHealthStatus:
    if meta is None:
        return BarHealthStatus.UNKNOWN
    latest = last_trading_day(on_or_before=as_of)
    if meta.end.date() < latest:
        return BarHealthStatus.STALE
    return BarHealthStatus.OK


def status_label(status: BarHealthStatus) -> str:
    labels = {
        BarHealthStatus.OK: "✅ 最新",
        BarHealthStatus.STALE: "⚠️ 过期",
        BarHealthStatus.GAPS: "🔴 断层",
        BarHealthStatus.UNKNOWN: "—",
    }
    return labels[status]


def format_meta_date(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%Y-%m-%d")


def format_meta_datetime(value: datetime | None, *, minute: bool = False) -> str:
    if value is None:
        return "—"
    if minute:
        return value.strftime("%Y-%m-%d %H:%M")
    return value.strftime("%Y-%m-%d")


def merge_missing_days(missing: list[date]) -> list[GapRange]:
    if not missing:
        return []
    sorted_days = sorted(missing)
    ranges: list[GapRange] = []
    range_start = sorted_days[0]
    range_end = sorted_days[0]
    count = 1

    for day in sorted_days[1:]:
        if (day - range_end).days == 1:
            range_end = day
            count += 1
            continue
        ranges.append(GapRange(start=range_start, end=range_end, missing_days=count))
        range_start = day
        range_end = day
        count = 1

    ranges.append(GapRange(start=range_start, end=range_end, missing_days=count))
    return ranges


def find_gaps(meta: BarMeta, bar_dates: set[date]) -> list[GapRange]:
    expected = trading_days_between(meta.start.date(), meta.end.date())
    missing = [day for day in expected if day not in bar_dates]
    return merge_missing_days(missing)


def inspect_bar_gaps(meta: BarMeta, bar_dates: set[date], *, as_of: date | None = None) -> BarGapResult:
    gaps = find_gaps(meta, bar_dates)
    expected_days = len(trading_days_between(meta.start.date(), meta.end.date()))
    actual_days = len(bar_dates)
    if gaps:
        status = BarHealthStatus.GAPS
    else:
        status = list_status(meta, as_of=as_of)
    return BarGapResult(
        status=status,
        gaps=gaps,
        expected_days=expected_days,
        actual_days=actual_days,
    )


def format_gap_ranges(gaps: list[GapRange]) -> str:
    if not gaps:
        return ""
    parts = [f"{gap.start.isoformat()}~{gap.end.isoformat()}" if gap.start != gap.end else gap.start.isoformat() for gap in gaps]
    return "、".join(parts)
