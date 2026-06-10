"""全 A 股标的同步。"""

from __future__ import annotations

from vnpy_ashare.app_db import universe_count
from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.universe import sync_universe


def sync_universe_job() -> JobResult:
    sync_universe(force=True)
    count = universe_count()
    return JobResult(success=True, message=f"已同步 {count} 只 A 股标的")
