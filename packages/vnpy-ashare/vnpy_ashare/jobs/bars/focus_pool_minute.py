"""关注池 1 分钟 K 线缺口检测与补全。"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from typing import Literal

from pydantic import Field
from vnpy.trader.constant import Exchange

from vnpy_ashare.config.runtime import format_vt_symbol_cn
from vnpy_ashare.data.bar_health import BarHealthStatus, BarMeta, bar_meta_from_overview, list_status
from vnpy_ashare.data.bar_store import get_scope_overview, iter_bar_overviews
from vnpy_ashare.data.bars import default_minute_download_start, download_period_bars
from vnpy_ashare.data.download_concurrency import download_max_workers, run_parallel_map
from vnpy_ashare.data.minute_periods import MINUTE_PERIOD, period_step
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.jobs.bars.local_fill import BatchFillProgress
from vnpy_ashare.jobs.core.progress import job_log, job_progress
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.services.focus_pool import load_focus_pool_stock_items, stock_items_from_vt_symbols
from vnpy_common.domain.base import FrozenModel

MinuteBarNeed = Literal["missing", "stale", "ok"]

__all__ = [
    "MinuteGapSummary",
    "batch_fill_focus_pool_minute_bars",
    "batch_fill_focus_pool_minute_job",
    "build_minute_bar_meta",
    "classify_minute_bar_need",
    "select_minute_fill_targets",
    "summarize_minute_gaps",
]


class MinuteGapSummary(FrozenModel):
    total: int = Field(description="检查标的数")
    missing: int = Field(description="无本地 1m 概览")
    stale: int = Field(description="1m 过期需增量")
    ok: int = Field(description="1m 已就绪")
    needs_fill: int = Field(description="missing + stale")

    @property
    def message(self) -> str:
        if self.total == 0:
            return "关注池为空"
        if self.needs_fill == 0:
            return f"关注池 {self.total} 只 1m K 均已就绪"
        parts = [f"缺 1m {self.missing} 只", f"需补全 {self.stale} 只"]
        return f"关注池 {self.total} 只：{' · '.join(parts)}"


class BatchMinuteFillResult(FrozenModel):
    attempted: int = Field(description="尝试补全数量")
    success: int = Field(description="成功数量")
    failed: list[str] = Field(description="失败标的")
    bars_added: int = Field(description="新增 K 线根数")
    up_to_date: int = Field(description="已是最新数量")

    @property
    def message(self) -> str:
        if self.attempted == 0:
            return "关注池 1m K 均已就绪，无需补全"
        parts = [f"1m 补全完成：成功 {self.success}/{self.attempted}"]
        if self.bars_added:
            parts.append(f"新增 {self.bars_added} 根")
        if self.up_to_date:
            parts.append(f"{self.up_to_date} 只已是最新")
        if self.failed:
            preview = "、".join(self.failed[:5])
            suffix = "…" if len(self.failed) > 5 else ""
            parts.append(f"失败 {len(self.failed)}（{preview}{suffix}）")
        return "，".join(parts)


def build_minute_bar_meta() -> dict[tuple[str, Exchange], BarMeta]:
    meta: dict[tuple[str, Exchange], BarMeta] = {}
    for row in iter_bar_overviews(scope=MINUTE_PERIOD):
        meta[(row.symbol, row.exchange)] = bar_meta_from_overview(row)
    return meta


def classify_minute_bar_need(item: StockItem, meta: BarMeta | None) -> MinuteBarNeed:
    if meta is None:
        overview = get_scope_overview(item.symbol, item.exchange, MINUTE_PERIOD)
        if overview is None:
            return "missing"
        meta = bar_meta_from_overview(overview)
    status = list_status(meta)
    if status == BarHealthStatus.STALE:
        return "stale"
    if status == BarHealthStatus.UNKNOWN:
        return "missing"
    return "ok"


def select_minute_fill_targets(
    items: list[StockItem],
    bar_meta: dict[tuple[str, Exchange], BarMeta],
) -> list[StockItem]:
    targets: list[StockItem] = []
    for item in items:
        meta = bar_meta.get((item.symbol, item.exchange))
        need = classify_minute_bar_need(item, meta)
        if need in {"missing", "stale"}:
            targets.append(item)
    return targets


def summarize_minute_gaps(items: list[StockItem]) -> MinuteGapSummary:
    if not items:
        return MinuteGapSummary(total=0, missing=0, stale=0, ok=0, needs_fill=0)
    bar_meta = build_minute_bar_meta()
    missing = stale = ok = 0
    for item in items:
        meta = bar_meta.get((item.symbol, item.exchange))
        need = classify_minute_bar_need(item, meta)
        if need == "missing":
            missing += 1
        elif need == "stale":
            stale += 1
        else:
            ok += 1
    return MinuteGapSummary(
        total=len(items),
        missing=missing,
        stale=stale,
        ok=ok,
        needs_fill=missing + stale,
    )


def summarize_minute_gaps_for_vt_symbols(vt_symbols: list[str] | tuple[str, ...]) -> MinuteGapSummary:
    return summarize_minute_gaps(stock_items_from_vt_symbols(vt_symbols))


class _MinuteFillOutcome(FrozenModel):
    label: str = Field(description="展示名")
    success: bool = Field(description="是否成功")
    added: int = Field(description="新增根数")
    failed: bool = Field(description="是否失败")


def fill_focus_pool_minute_bar(
    item: StockItem,
    bar_meta: dict[tuple[str, Exchange], BarMeta],
    *,
    end: datetime | None = None,
) -> int:
    """全量或增量补全单标的 1m K，返回新增根数。"""
    end_dt = end or datetime.now()
    meta = bar_meta.get((item.symbol, item.exchange))
    need = classify_minute_bar_need(item, meta)
    if need == "ok":
        return 0
    if need == "missing" or meta is None:
        start = default_minute_download_start(end_dt)
    else:
        start = meta.end + period_step(MINUTE_PERIOD)
        if start >= end_dt:
            return 0
    return download_period_bars(
        symbol=item.symbol,
        exchange=item.exchange,
        period=MINUTE_PERIOD,
        start=start,
        end=end_dt,
        output=lambda _msg: None,
    )


def _fill_minute_item(
    item: StockItem,
    bar_meta: dict[tuple[str, Exchange], BarMeta],
    *,
    end: datetime | None,
) -> _MinuteFillOutcome:
    label = format_vt_symbol_cn(item.symbol, item.exchange)
    try:
        added = fill_focus_pool_minute_bar(item, bar_meta, end=end)
        return _MinuteFillOutcome(label=label, success=True, added=added, failed=False)
    except Exception:
        return _MinuteFillOutcome(label=label, success=False, added=0, failed=True)


def batch_fill_focus_pool_minute_bars(
    items: list[StockItem],
    *,
    delay: float = 0.5,
    progress: Callable[[BatchFillProgress], None] | None = None,
    end: datetime | None = None,
    max_workers: int | None = None,
) -> BatchMinuteFillResult:
    if not items:
        return BatchMinuteFillResult(attempted=0, success=0, failed=[], bars_added=0, up_to_date=0)

    bar_meta = build_minute_bar_meta()
    targets = select_minute_fill_targets(items, bar_meta)
    if not targets:
        return BatchMinuteFillResult(attempted=0, success=0, failed=[], bars_added=0, up_to_date=len(items))

    total = len(targets)
    workers = max_workers if max_workers is not None else min(download_max_workers(item_count=total), 2)

    def on_complete(index: int, item: StockItem, outcome: _MinuteFillOutcome) -> None:
        if progress is not None:
            progress(BatchFillProgress(current=index, total=total, label=outcome.label))

    if workers <= 1:
        outcomes: list[_MinuteFillOutcome] = []
        for index, item in enumerate(targets, start=1):
            outcome = _fill_minute_item(item, bar_meta, end=end)
            outcomes.append(outcome)
            if progress is not None:
                progress(BatchFillProgress(current=index, total=total, label=outcome.label))
            if index < total and delay > 0:
                time.sleep(delay)
    else:
        outcomes = run_parallel_map(
            targets,
            lambda item: _fill_minute_item(item, bar_meta, end=end),
            max_workers=workers,
            on_complete=on_complete,
        )

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

    return BatchMinuteFillResult(
        attempted=total,
        success=success,
        failed=failed,
        bars_added=bars_added,
        up_to_date=up_to_date,
    )


def batch_fill_focus_pool_minute_job(
    *,
    vt_symbols: tuple[str, ...] | None = None,
) -> JobResult:
    """定时/CLI：为短线观察组 + 持仓补全 1m K。"""
    try:
        get_tushare_pro()
    except TushareNotConfiguredError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    if vt_symbols:
        items = stock_items_from_vt_symbols(vt_symbols)
    else:
        items = load_focus_pool_stock_items()

    if not items:
        return JobResult(success=True, message="关注池为空，跳过 1m 补全")

    summary = summarize_minute_gaps(items)
    if summary.needs_fill == 0:
        job_log(summary.message)
        return JobResult(success=True, message=summary.message)

    job_log(f"待补全 1m K：{summary.needs_fill}/{summary.total} 只")

    def on_progress(progress: BatchFillProgress) -> None:
        job_progress(progress.current, progress.total, progress.label)

    result = batch_fill_focus_pool_minute_bars(items, delay=0.5, progress=on_progress)
    success = len(result.failed) == 0
    return JobResult(success=success, message=result.message)
