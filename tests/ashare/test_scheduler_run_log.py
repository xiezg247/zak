"""调度器执行日志（过程输出）测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.jobs.core.progress import bind_job_log, job_log, job_progress
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.scheduler.manager import TaskSchedulerManager


class JobProgressTests(unittest.TestCase):
    def test_job_log_without_binding_is_silent(self) -> None:
        job_log("ignored")

    def test_job_log_routes_to_sink(self) -> None:
        lines: list[str] = []
        reset = bind_job_log(lines.append)
        try:
            job_log("hello")
            job_progress(2, 5, "600519.SSE")
        finally:
            reset()
        self.assertEqual(lines[0], "hello")
        self.assertEqual(lines[1], "600519.SSE (2/5)")


class SchedulerRunLogTests(unittest.TestCase):
    def test_wrap_job_emits_progress_lines(self) -> None:
        manager = TaskSchedulerManager()

        def _fake_run_job(job_id: str, *, force: bool = False, engine=None) -> JobResult:
            job_log("step-1")
            job_log("step-2")
            return JobResult(success=True, message="done")

        with patch("vnpy_ashare.scheduler.manager.run_job", side_effect=_fake_run_job):
            manager._wrap_job("sync_universe")

        records = manager.list_run_log(limit=1)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertFalse(record.running)
        self.assertIn("step-1", record.detail_lines)
        self.assertIn("step-2", record.detail_lines)
        self.assertIn("[结束] 成功", record.detail_lines[-1])


if __name__ == "__main__":
    unittest.main()
