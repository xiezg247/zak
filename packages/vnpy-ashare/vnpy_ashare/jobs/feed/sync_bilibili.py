"""B 站订阅同步 Job。"""

from __future__ import annotations

from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.services.feed import run_feed_sync


def sync_bilibili_feed_job(*, force: bool = False) -> JobResult:
  """同步所有启用的 B 站 UP 订阅。"""
  del force
  return run_feed_sync()
