"""本地页批量补全过期日 K、批量修复内部断层。"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database

from vnpy_ashare.config import format_vt_symbol_cn
from vnpy_ashare.data.bar_health import (
    BarGapResult,
    BarHealthStatus,
    BarMeta,
    GapRange,
    inspect_bar_gaps,
    list_status,
)
from vnpy_ashare.data.bar_store import get_scope_overview
from vnpy_ashare.data.bars import download_bars
from vnpy_ashare.data.download_concurrency import download_max_workers, run_parallel_map
from vnpy_ashare.domain.models import StockItem


@dataclass(frozen=True)
class BatchFillProgress:
    current: int
    total: int
    label: str


@dataclass(frozen=True)
class BatchFillResult:
    attempted: int
    success: int
    failed: list[str]
    bars_added: int
    up_to_date: int

    @property
    def message(self) -> str:
        if self.attempted == 0:
            return "没有需要补全的过期日 K"
        parts = [f"批量补全完成：成功 {self.success}/{self.attempted}"]
        if self.bars_added:
            parts.append(f"新增 {self.bars_added} 根")
        if self.up_to_date:
            parts.append(f"{self.up_to_date} 只已是最新")
        if self.failed:
            preview = "、".join(self.failed[:5])
            suffix = "…" if len(self.failed) > 5 else ""
            parts.append(f"失败 {len(self.failed)}（{preview}{suffix}）")
        return "，".join(parts)


def select_stale_daily_items(
    stocks: list[StockItem],
    bar_meta: dict[tuple[str, Exchange], BarMeta],
    *,
    as_of: date | None = None,
) -> list[StockItem]:
    """筛选列表中 end 早于最近交易日的日 K 标的。"""
    stale: list[StockItem] = []
    for item in stocks:
        key = (item.symbol, item.exchange)
        meta = bar_meta.get(key)
        if meta is None:
            continue
        if list_status(meta, as_of=as_of) == BarHealthStatus.STALE:
            stale.append(item)
    return stale


def count_stale_daily_items(
    stocks: list[StockItem],
    bar_meta: dict[tuple[str, Exchange], BarMeta],
    *,
    as_of: date | None = None,
) -> int:
    return len(select_stale_daily_items(stocks, bar_meta, as_of=as_of))


def fill_stale_daily_bar(
    item: StockItem,
    meta: BarMeta,
    *,
    end: datetime | None = None,
) -> int:
    """增量补全单标的日 K，返回新增根数（0 表示已最新）。"""
    end_dt = end or datetime.now()
    start = meta.end + timedelta(days=1)
    if start.date() > end_dt.date():
        return 0
    return download_bars(
        symbol=item.symbol,
        exchange=item.exchange,
        interval=Interval.DAILY,
        start=start,
        end=end_dt,
        output=lambda _msg: None,
    )


@dataclass(frozen=True)
class _StaleFillOutcome:
    label: str
    success: bool
    added: int
    failed: bool


def _fill_stale_item(
    item: StockItem,
    bar_meta: dict[tuple[str, Exchange], BarMeta],
    *,
    end: datetime | None,
) -> _StaleFillOutcome:
    label = format_vt_symbol_cn(item.symbol, item.exchange)
    key = (item.symbol, item.exchange)
    meta = bar_meta.get(key)
    if meta is None:
        overview = get_scope_overview(item.symbol, item.exchange, "daily")
        if overview is None:
            return _StaleFillOutcome(label=label, success=False, added=0, failed=True)
        meta = BarMeta(start=overview.start, end=overview.end, count=overview.count)
    try:
        added = fill_stale_daily_bar(item, meta, end=end)
        return _StaleFillOutcome(label=label, success=True, added=added, failed=False)
    except Exception:
        return _StaleFillOutcome(label=label, success=False, added=0, failed=True)


def batch_fill_stale_daily_bars(
    items: list[StockItem],
    bar_meta: dict[tuple[str, Exchange], BarMeta],
    *,
    delay: float = 0.3,
    progress: Callable[[BatchFillProgress], None] | None = None,
    end: datetime | None = None,
    max_workers: int | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> BatchFillResult:
    """对过期标的增量补全日 K（多 worker 并发，单 worker 时保留 delay）。"""
    if not items:
        return BatchFillResult(attempted=0, success=0, failed=[], bars_added=0, up_to_date=0)

    total = len(items)
    workers = max_workers if max_workers is not None else download_max_workers(item_count=total)
    completed = 0

    def on_complete(_index: int, item: StockItem, outcome: _StaleFillOutcome) -> None:
        nonlocal completed
        completed += 1
        if progress is not None:
            progress(BatchFillProgress(current=completed, total=total, label=outcome.label))

    if workers <= 1:
        outcomes: list[_StaleFillOutcome] = []
        for index, item in enumerate(items, start=1):
            if should_cancel is not None and should_cancel():
                break
            outcome = _fill_stale_item(item, bar_meta, end=end)
            outcomes.append(outcome)
            if progress is not None:
                progress(BatchFillProgress(current=index, total=total, label=outcome.label))
            if index < total and delay > 0:
                time.sleep(delay)
    else:

        def worker(item: StockItem) -> _StaleFillOutcome:
            return _fill_stale_item(item, bar_meta, end=end)

        outcomes = run_parallel_map(items, worker, max_workers=workers, on_complete=on_complete)

    success = 0
    failed: list[str] = []
    bars_added = 0
    up_to_date = 0
    for outcome in outcomes:
        if outcome.failed:
            failed.append(outcome.label)
            continue
        success += 1
        if outcome.added == 0:
            up_to_date += 1
        else:
            bars_added += outcome.added

    return BatchFillResult(
        attempted=total,
        success=success,
        failed=failed,
        bars_added=bars_added,
        up_to_date=up_to_date,
    )


def load_daily_bar_dates(
    symbol: str,
    exchange: Exchange,
    meta: BarMeta,
) -> set[date]:
    """读取本地日 K 已有交易日集合。"""
    database = get_database()
    bars = database.load_bar_data(
        symbol,
        exchange,
        Interval.DAILY,
        meta.start,
        meta.end,
    )
    return {bar.datetime.date() for bar in bars}


def inspect_item_gaps(
    item: StockItem,
    meta: BarMeta,
    *,
    as_of: date | None = None,
) -> BarGapResult:
    bar_dates = load_daily_bar_dates(item.symbol, item.exchange, meta)
    return inspect_bar_gaps(meta, bar_dates, as_of=as_of)


def fill_gap_ranges(
    item: StockItem,
    gaps: list[GapRange],
    *,
    anchor_time: datetime | None = None,
) -> int:
    """按断层区间下载日 K，返回新增根数。"""
    if not gaps:
        return 0
    ref = anchor_time or datetime.now().replace(hour=15, minute=0, second=0, microsecond=0)
    total = 0
    for gap in gaps:
        start = datetime.combine(gap.start, ref.time())
        end = datetime.combine(gap.end, ref.time())
        total += download_bars(
            symbol=item.symbol,
            exchange=item.exchange,
            interval=Interval.DAILY,
            start=start,
            end=end,
            output=lambda _msg: None,
        )
    return total


@dataclass(frozen=True)
class BatchGapFillProgress:
    phase: str
    current: int
    total: int
    label: str


@dataclass(frozen=True)
class BatchGapFillResult:
    scanned: int
    with_gaps: int
    attempted: int
    success: int
    failed: list[str]
    bars_added: int
    gap_ranges_fixed: int

    @property
    def message(self) -> str:
        if self.scanned == 0:
            return "列表内无日 K 可扫描"
        if self.with_gaps == 0:
            return f"已扫描 {self.scanned} 只，未发现内部断层"
        parts = [f"批量修复断层完成：成功 {self.success}/{self.attempted}"]
        if self.gap_ranges_fixed:
            parts.append(f"修复 {self.gap_ranges_fixed} 处断层")
        if self.bars_added:
            parts.append(f"新增 {self.bars_added} 根")
        if self.failed:
            preview = "、".join(self.failed[:5])
            suffix = "…" if len(self.failed) > 5 else ""
            parts.append(f"失败 {len(self.failed)}（{preview}{suffix}）")
        return "，".join(parts)


def count_scannable_daily_items(
    stocks: list[StockItem],
    bar_meta: dict[tuple[str, Exchange], BarMeta],
) -> int:
    return sum(1 for item in stocks if bar_meta.get((item.symbol, item.exchange)))


@dataclass(frozen=True)
class _GapFixOutcome:
    label: str
    success: bool
    added: int
    gap_count: int


def _fix_gap_item(entry: tuple[StockItem, BarMeta, list[GapRange]]) -> _GapFixOutcome:
    item, meta, gaps = entry
    label = format_vt_symbol_cn(item.symbol, item.exchange)
    try:
        added = fill_gap_ranges(item, gaps, anchor_time=meta.start)
        return _GapFixOutcome(label=label, success=True, added=added, gap_count=len(gaps))
    except Exception:
        return _GapFixOutcome(label=label, success=False, added=0, gap_count=0)


def batch_fill_gap_daily_bars(
    stocks: list[StockItem],
    bar_meta: dict[tuple[str, Exchange], BarMeta],
    *,
    delay: float = 0.3,
    progress: Callable[[BatchGapFillProgress], None] | None = None,
    as_of: date | None = None,
    max_workers: int | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> BatchGapFillResult:
    """扫描列表内日 K 并修复内部断层。"""
    candidates = [item for item in stocks if bar_meta.get((item.symbol, item.exchange)) is not None]
    if not candidates:
        return BatchGapFillResult(
            scanned=0,
            with_gaps=0,
            attempted=0,
            success=0,
            failed=[],
            bars_added=0,
            gap_ranges_fixed=0,
        )

    with_gaps_items: list[tuple[StockItem, BarMeta, list[GapRange]]] = []
    scanned = 0

    for index, item in enumerate(candidates, start=1):
        if should_cancel is not None and should_cancel():
            break
        label = format_vt_symbol_cn(item.symbol, item.exchange)
        if progress is not None:
            progress(BatchGapFillProgress("scan", index, len(candidates), label))

        meta = bar_meta[(item.symbol, item.exchange)]
        try:
            gap_result = inspect_item_gaps(item, meta, as_of=as_of)
            scanned += 1
            if gap_result.status == BarHealthStatus.GAPS and gap_result.gaps:
                with_gaps_items.append((item, meta, gap_result.gaps))
        except Exception:
            scanned += 1

        if index < len(candidates) and delay > 0:
            time.sleep(delay * 0.1)

    if not with_gaps_items:
        return BatchGapFillResult(
            scanned=scanned,
            with_gaps=0,
            attempted=0,
            success=0,
            failed=[],
            bars_added=0,
            gap_ranges_fixed=0,
        )

    success = 0
    failed: list[str] = []
    bars_added = 0
    gap_ranges_fixed = 0
    total_fix = len(with_gaps_items)
    workers = max_workers if max_workers is not None else download_max_workers(item_count=total_fix)
    completed = 0

    def on_fix_complete(_index: int, entry: tuple[StockItem, BarMeta, list[GapRange]], outcome: _GapFixOutcome) -> None:
        nonlocal completed
        completed += 1
        if progress is not None:
            progress(BatchGapFillProgress("fix", completed, total_fix, outcome.label))

    if workers <= 1:
        outcomes: list[_GapFixOutcome] = []
        for index, entry in enumerate(with_gaps_items, start=1):
            if should_cancel is not None and should_cancel():
                break
            outcome = _fix_gap_item(entry)
            outcomes.append(outcome)
            if progress is not None:
                progress(BatchGapFillProgress("fix", index, total_fix, outcome.label))
            if index < total_fix and delay > 0:
                time.sleep(delay)
    else:
        outcomes = run_parallel_map(
            with_gaps_items,
            _fix_gap_item,
            max_workers=workers,
            on_complete=on_fix_complete,
        )

    for outcome in outcomes:
        if not outcome.success:
            failed.append(outcome.label)
            continue
        bars_added += outcome.added
        gap_ranges_fixed += outcome.gap_count
        success += 1

    return BatchGapFillResult(
        scanned=scanned,
        with_gaps=len(with_gaps_items),
        attempted=total_fix,
        success=success,
        failed=failed,
        bars_added=bars_added,
        gap_ranges_fixed=gap_ranges_fixed,
    )
