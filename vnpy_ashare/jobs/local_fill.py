"""本地页批量补全过期日 K。"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from vnpy.trader.constant import Exchange, Interval

from vnpy_ashare.bar_health import BarHealthStatus, BarMeta, list_status
from vnpy_ashare.bar_store import get_scope_overview
from vnpy_ashare.bars import download_bars
from vnpy_ashare.config import format_vt_symbol_cn
from vnpy_ashare.models import StockItem


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


def batch_fill_stale_daily_bars(
    items: list[StockItem],
    bar_meta: dict[tuple[str, Exchange], BarMeta],
    *,
    delay: float = 0.3,
    progress: Callable[[BatchFillProgress], None] | None = None,
    end: datetime | None = None,
) -> BatchFillResult:
    """对过期标的逐个增量补全日 K。"""
    if not items:
        return BatchFillResult(attempted=0, success=0, failed=[], bars_added=0, up_to_date=0)

    success = 0
    failed: list[str] = []
    bars_added = 0
    up_to_date = 0
    total = len(items)

    for index, item in enumerate(items, start=1):
        label = format_vt_symbol_cn(item.symbol, item.exchange)
        if progress is not None:
            progress(BatchFillProgress(current=index, total=total, label=label))

        key = (item.symbol, item.exchange)
        meta = bar_meta.get(key)
        if meta is None:
            overview = get_scope_overview(item.symbol, item.exchange, "daily")
            if overview is None:
                failed.append(label)
                continue
            meta = BarMeta(start=overview.start, end=overview.end, count=overview.count)

        try:
            added = fill_stale_daily_bar(item, meta, end=end)
            if added == 0:
                up_to_date += 1
            else:
                bars_added += added
            success += 1
        except Exception:
            failed.append(label)

        if index < total and delay > 0:
            time.sleep(delay)

    return BatchFillResult(
        attempted=total,
        success=success,
        failed=failed,
        bars_added=bars_added,
        up_to_date=up_to_date,
    )
