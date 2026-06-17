"""任务基础设施：执行结果与进度日志。"""

from vnpy_ashare.jobs.core.progress import bind_job_log, job_log, job_progress
from vnpy_ashare.jobs.core.result import JobResult

__all__ = [
    "JobResult",
    "bind_job_log",
    "job_log",
    "job_progress",
]
