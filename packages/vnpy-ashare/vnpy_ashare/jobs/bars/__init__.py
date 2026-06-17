"""日 K 下载与本地补全。"""

from vnpy_ashare.jobs.bars.batch_fill import batch_fill_downloaded_stale_job, build_daily_bar_meta
from vnpy_ashare.jobs.bars.download import (
    batch_download_universe_daily_bars,
    load_universe_stock_items,
    parse_universe_daily_start,
    select_universe_daily_targets,
)
from vnpy_ashare.jobs.bars.local_fill import (
    BatchFillProgress,
    BatchFillResult,
    BatchGapFillProgress,
    BatchGapFillResult,
    batch_fill_gap_daily_bars,
    batch_fill_stale_daily_bars,
    count_scannable_daily_items,
    count_stale_daily_items,
    fill_gap_ranges,
    fill_stale_daily_bar,
    inspect_item_gaps,
    load_daily_bar_dates,
    select_stale_daily_items,
)

__all__ = [
    "BatchFillProgress",
    "BatchFillResult",
    "BatchGapFillProgress",
    "BatchGapFillResult",
    "batch_download_universe_daily_bars",
    "batch_fill_downloaded_stale_job",
    "batch_fill_gap_daily_bars",
    "batch_fill_stale_daily_bars",
    "build_daily_bar_meta",
    "count_scannable_daily_items",
    "count_stale_daily_items",
    "fill_gap_ranges",
    "fill_stale_daily_bar",
    "inspect_item_gaps",
    "load_daily_bar_dates",
    "load_universe_stock_items",
    "parse_universe_daily_start",
    "select_stale_daily_items",
    "select_universe_daily_targets",
]
