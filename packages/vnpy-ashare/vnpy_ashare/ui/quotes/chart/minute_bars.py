"""分 K 会话缓存与增量 diff（自选页 ChartPanel 使用）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData

from vnpy_ashare.data.bar_access import get_period_overview

LIVE_MINUTE_TAIL_COUNT = 5


def prepare_chart_bars(bars: list[BarData]) -> list[BarData]:
    """排序并去重，避免 BarManager 按 datetime 合并时索引错位。"""
    if not bars:
        return []
    unique: dict[datetime, BarData] = {}
    for bar in bars:
        unique[bar.datetime] = bar
    return [unique[dt] for dt in sorted(unique.keys())]


class MinuteBarDiff(str, Enum):
    NOOP = "noop"
    TAIL_PATCH = "tail_patch"
    REPLACE = "replace"


@dataclass(frozen=True)
class OverviewFingerprint:
    start: datetime
    end: datetime


@dataclass
class MinuteBarChange:
    diff: MinuteBarDiff
    bars: list[BarData]
    patch_from: int = 0


def bar_values_equal(left: BarData, right: BarData) -> bool:
    return (
        left.datetime == right.datetime
        and left.open_price == right.open_price
        and left.high_price == right.high_price
        and left.low_price == right.low_price
        and left.close_price == right.close_price
        and left.volume == right.volume
    )


def bars_list_equal(left: list[BarData], right: list[BarData]) -> bool:
    if len(left) != len(right):
        return False
    return all(bar_values_equal(a, b) for a, b in zip(left, right, strict=True))


def merge_minute_bars(existing: list[BarData], incoming: list[BarData]) -> list[BarData]:
    """按 datetime 合并去重并排序。"""
    if not incoming:
        return list(existing)
    if not existing:
        return prepare_chart_bars(incoming)
    merged: dict[datetime, BarData] = {bar.datetime: bar for bar in existing}
    for bar in incoming:
        merged[bar.datetime] = bar
    return [merged[dt] for dt in sorted(merged.keys())]


def compute_minute_bar_change(
    existing: list[BarData],
    incoming: list[BarData],
) -> MinuteBarChange:
    """对比合并前后序列，决定全量替换或尾部 patch。"""
    merged = merge_minute_bars(existing, incoming)
    if bars_list_equal(existing, merged):
        return MinuteBarChange(MinuteBarDiff.NOOP, existing)

    if not merged:
        return MinuteBarChange(MinuteBarDiff.REPLACE, merged)

    if not existing:
        return MinuteBarChange(MinuteBarDiff.REPLACE, merged)

    min_len = min(len(existing), len(merged))
    first_diff = min_len
    for index in range(min_len):
        if not bar_values_equal(existing[index], merged[index]):
            first_diff = index
            break

    if first_diff == min_len and len(merged) == len(existing):
        return MinuteBarChange(MinuteBarDiff.NOOP, existing)

    if first_diff >= len(existing) - 1 and all(
        bar_values_equal(existing[index], merged[index]) for index in range(first_diff)
    ):
        return MinuteBarChange(MinuteBarDiff.TAIL_PATCH, merged, patch_from=first_diff)

    return MinuteBarChange(MinuteBarDiff.REPLACE, merged)


@dataclass
class MinuteBarSession:
    """分 K 内存会话：缓存已渲染序列与本地 overview 指纹。"""

    key: tuple[str, Exchange, str] | None = None
    bars: list[BarData] = field(default_factory=list)
    from_local: bool = False
    overview: OverviewFingerprint | None = None
    start_text: str = ""
    end_text: str = ""

    def reset(self) -> None:
        self.key = None
        self.bars = []
        self.from_local = False
        self.overview = None
        self.start_text = ""
        self.end_text = ""

    def matches_key(self, key: tuple[str, Exchange, str]) -> bool:
        return self.key == key and bool(self.bars)

    def bar_count(self) -> int:
        return len(self.bars)

    def overview_unchanged(self, symbol: str, exchange: Exchange, period: str) -> bool:
        """本地分 K 的 overview 是否与缓存一致（未下载/补全则跳过刷新）。"""
        if not self.from_local or self.overview is None:
            return False
        if self.key != (symbol, exchange, period):
            return False
        overview = get_period_overview(symbol, exchange, period)
        if overview is None:
            return False
        return OverviewFingerprint(overview.start, overview.end) == self.overview

    def apply_loaded(
        self,
        *,
        key: tuple[str, Exchange, str],
        bars: list[BarData],
        from_local: bool,
        start: datetime | None,
        end: datetime | None,
    ) -> None:
        self.key = key
        self.bars = list(bars)
        self.from_local = from_local
        if from_local and start is not None and end is not None:
            self.overview = OverviewFingerprint(start, end)
            self.start_text = start.strftime("%Y-%m-%d")
            self.end_text = end.strftime("%Y-%m-%d %H:%M")
        else:
            self.overview = None
            self.start_text = ""
            self.end_text = ""

    def adopt_bars(self, bars: list[BarData]) -> None:
        self.bars = list(bars)
