"""scheduler job_finished_hook 测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.scheduler.manager import TaskSchedulerManager


class SchedulerNotifyHookTest(unittest.TestCase):
    def test_add_job_finished_hook_invoked(self) -> None:
        mgr = TaskSchedulerManager()
        calls: list[tuple[str, JobResult]] = []
        mgr.add_job_finished_hook(lambda jid, res: calls.append((jid, res)))
        mgr._job_finished_hooks[0]("screen_intraday", JobResult(success=True, message="ok", skipped=False))
        self.assertEqual(calls[0][0], "screen_intraday")
        self.assertTrue(calls[0][1].success)

    def test_get_job_name(self) -> None:
        mgr = TaskSchedulerManager()
        self.assertEqual(mgr.get_job_name("screen_intraday"), "盘中自动选股")
        self.assertEqual(mgr.get_job_name("unknown"), "unknown")
