"""本地日 K 覆盖与健康状态。

状态语义（列表页 vs 选中扫描）::

    OK / STALE / UNKNOWN — ``list_status`` 由 meta.end 与最近交易日比较
    GAPS — 须 ``inspect_bar_gaps`` 异步扫描 bar_dates 后才能判定
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from vnpy_ashare.domain.calendar import last_trading_day, trading_days_between


class BarHealthStatus(str, Enum):
    """日 K 健康状态。"""

    OK = "ok"
    STALE = "stale"
    GAPS = "gaps"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BarMeta:
    """本地 K 线元数据（起止日期与条数）。"""

    start: datetime
    end: datetime
    count: int


@dataclass(frozen=True)
class GapRange:
    """连续缺失交易日区间。"""

    start: date
    end: date
    missing_days: int


@dataclass(frozen=True)
class BarGapResult:
    """断层扫描结果（含期望/实际交易日数）。"""

    status: BarHealthStatus
    gaps: list[GapRange]
    expected_days: int
    actual_days: int


def list_status(meta: BarMeta | None, *, as_of: date | None = None) -> BarHealthStatus:
    """列表页快速判定：无数据 UNKNOWN；结束日早于最近交易日 STALE；否则 OK。"""
    if meta is None:
        return BarHealthStatus.UNKNOWN
    latest = last_trading_day(on_or_before=as_of)
    if meta.end.date() < latest:
        return BarHealthStatus.STALE
    return BarHealthStatus.OK


def status_label(status: BarHealthStatus) -> str:
    """状态 → 表格展示文案（含 emoji）。"""
    labels = {
        BarHealthStatus.OK: "✅ 最新",
        BarHealthStatus.STALE: "⚠️ 过期",
        BarHealthStatus.GAPS: "🔴 断层",
        BarHealthStatus.UNKNOWN: "—",
    }
    return labels[status]


def format_meta_date(value: datetime | None) -> str:
    """格式化 meta 日期为 yyyy-MM-dd。"""
    if value is None:
        return "—"
    return value.strftime("%Y-%m-%d")


def format_meta_datetime(value: datetime | None, *, minute: bool = False) -> str:
    """格式化 meta 日期时间；``minute=True`` 时含时分。"""
    if value is None:
        return "—"
    if minute:
        return value.strftime("%Y-%m-%d %H:%M")
    return value.strftime("%Y-%m-%d")


def merge_missing_days(missing: list[date]) -> list[GapRange]:
    """将离散缺失日合并为连续区间。"""
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
    """在 meta 覆盖范围内找出缺失的交易日。"""
    expected = trading_days_between(meta.start.date(), meta.end.date())
    missing = [day for day in expected if day not in bar_dates]
    return merge_missing_days(missing)


def inspect_bar_gaps(meta: BarMeta, bar_dates: set[date], *, as_of: date | None = None) -> BarGapResult:
    """选中行异步扫描：有断层则 GAPS，否则回退 ``list_status``。"""
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
    """将断层区间格式化为 UI 展示字符串。"""
    if not gaps:
        return ""
    parts = [f"{gap.start.isoformat()}~{gap.end.isoformat()}" if gap.start != gap.end else gap.start.isoformat() for gap in gaps]
    return "、".join(parts)
