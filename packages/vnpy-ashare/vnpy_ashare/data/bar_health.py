"""本地日 K 覆盖与健康状态。

状态语义（列表页 vs 选中扫描）::

    OK / STALE / UNKNOWN — ``list_status`` 由 meta.end 与最近交易日比较
    GAPS — 须 ``inspect_bar_gaps`` 异步扫描 bar_dates 后才能判定
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData

from vnpy_ashare.data.bar_store import PeriodBarOverview
from vnpy_ashare.domain.time.calendar import last_trading_day, trading_days_between
from vnpy_ashare.storage.repositories.symbol_suspend import load_suspend_days

# 本地日 K 统一起点：早于该日的不展示、不参与断层扫描
UNIFIED_BAR_START = datetime(2020, 1, 2)


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


def effective_bar_start(value: datetime | None) -> datetime | None:
    """展示/扫描用起始日：不早于 UNIFIED_BAR_START，晚于则取实际。"""
    if value is None:
        return None
    if value.date() < UNIFIED_BAR_START.date():
        return UNIFIED_BAR_START
    return value


def bar_meta_from_overview(row: PeriodBarOverview) -> BarMeta:
    """由 PeriodBarOverview 构建 BarMeta。"""
    start = effective_bar_start(row.start)
    assert start is not None
    return BarMeta(start=start, end=row.end, count=row.count)


def clip_bars_from_unified_start(bars: list[BarData]) -> list[BarData]:
    """丢弃统一起点之前的 K 线。"""
    floor = UNIFIED_BAR_START.date()
    return [bar for bar in bars if bar.datetime.date() >= floor]


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


def gap_scan_range(meta: BarMeta, bar_dates: set[date]) -> tuple[date, date]:
    """断层扫描区间：起始于 effective_bar_start，忽略 2020-01-02 之前。"""
    floor = effective_bar_start(meta.start)
    assert floor is not None
    scan_start = floor.date()
    if bar_dates:
        scan_start = max(scan_start, min(bar_dates))
    scan_end = max(meta.end.date(), max(bar_dates) if bar_dates else meta.end.date())
    if scan_start > scan_end:
        return floor.date(), meta.end.date()
    return scan_start, scan_end


def expected_trading_days_for_bars(
    scan_start: date,
    scan_end: date,
    *,
    symbol: str | None = None,
    exchange: Exchange | str | None = None,
) -> list[date]:
    """扫描区间内应存在的交易日（排除已知停牌日）。"""
    expected = trading_days_between(scan_start, scan_end)
    if symbol is None or exchange is None:
        return expected
    suspend_days = load_suspend_days(symbol, exchange, scan_start, scan_end)
    if not suspend_days:
        return expected
    return [day for day in expected if day not in suspend_days]


def find_gaps(
    meta: BarMeta,
    bar_dates: set[date],
    *,
    expected: list[date] | None = None,
    symbol: str | None = None,
    exchange: Exchange | str | None = None,
) -> list[GapRange]:
    """在扫描区间内找出缺失的交易日。"""
    if expected is None:
        scan_start, scan_end = gap_scan_range(meta, bar_dates)
        expected = expected_trading_days_for_bars(
            scan_start,
            scan_end,
            symbol=symbol,
            exchange=exchange,
        )
    missing = [day for day in expected if day not in bar_dates]
    return merge_missing_days(missing)


def inspect_bar_gaps(
    meta: BarMeta,
    bar_dates: set[date],
    *,
    as_of: date | None = None,
    symbol: str | None = None,
    exchange: Exchange | str | None = None,
) -> BarGapResult:
    """选中行异步扫描：有断层则 GAPS，否则回退 ``list_status``。"""
    floor = UNIFIED_BAR_START.date()
    filtered_dates = {day for day in bar_dates if day >= floor}
    scan_start, scan_end = gap_scan_range(meta, filtered_dates)
    expected_days = expected_trading_days_for_bars(
        scan_start,
        scan_end,
        symbol=symbol,
        exchange=exchange,
    )
    gaps = find_gaps(
        meta,
        filtered_dates,
        expected=expected_days,
        symbol=symbol,
        exchange=exchange,
    )
    expected_count = len(expected_days)
    actual_days = len(filtered_dates)
    if gaps:
        status = BarHealthStatus.GAPS
    else:
        status = list_status(meta, as_of=as_of)
    return BarGapResult(
        status=status,
        gaps=gaps,
        expected_days=expected_count,
        actual_days=actual_days,
    )


def format_gap_ranges(gaps: list[GapRange]) -> str:
    """将断层区间格式化为 UI 展示字符串。"""
    if not gaps:
        return ""
    parts = [f"{gap.start.isoformat()}~{gap.end.isoformat()}" if gap.start != gap.end else gap.start.isoformat() for gap in gaps]
    return "、".join(parts)
