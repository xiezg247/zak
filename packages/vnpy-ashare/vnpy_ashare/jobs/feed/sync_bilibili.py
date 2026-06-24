"""B 站订阅同步 Job。"""

from __future__ import annotations

from datetime import datetime

from vnpy_ashare.domain.time.china import china_now
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.services.feed import run_feed_sync

BILIBILI_SYNC_START_HOUR = 8
BILIBILI_SYNC_END_HOUR = 20
BILIBILI_SYNC_INTERVAL_SECONDS = 300


def is_bilibili_sync_window(now: datetime | None = None) -> bool:
    """是否在每日 08:00–20:00 同步窗口内（不含 20:00）。"""
    dt = now or china_now()
    return BILIBILI_SYNC_START_HOUR <= dt.hour < BILIBILI_SYNC_END_HOUR


def sync_bilibili_feed_job(*, force: bool = False) -> JobResult:
    """同步所有启用的 B 站 UP 订阅。"""
    if not force and not is_bilibili_sync_window():
        return JobResult(
            success=True,
            skipped=True,
            message="非 08:00–20:00 时段，已跳过 B 站订阅同步",
        )
    return run_feed_sync()
