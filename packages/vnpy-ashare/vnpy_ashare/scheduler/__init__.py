"""定时任务调度。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnpy_ashare.scheduler.manager import JobRunRecord, JobStatus, TaskSchedulerManager

__all__ = ["JobRunRecord", "JobStatus", "TaskSchedulerManager"]


def __getattr__(name: str) -> object:
    if name in __all__:
        from vnpy_ashare.scheduler.manager import JobRunRecord, JobStatus, TaskSchedulerManager

        return {
            "JobRunRecord": JobRunRecord,
            "JobStatus": JobStatus,
            "TaskSchedulerManager": TaskSchedulerManager,
        }[name]
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
