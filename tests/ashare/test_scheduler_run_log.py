"""调度器执行日志（过程输出）测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.jobs.core.progress import bind_job_log, job_log, job_progress
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.scheduler.manager import TaskSchedulerManager, order_run_log_records


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


class RunLogOrderTests(unittest.TestCase):
    def test_order_completed_chronologically_running_at_end(self) -> None:
        from vnpy_ashare.scheduler.manager import JobRunRecord

        records = [
            JobRunRecord(
                started_at="2026-06-29 10:00:00",
                finished_at="2026-06-29 10:00:00",
                job_id="collect_quotes",
                job_name="行情采集",
                success=True,
                message="执行中…",
                running=True,
            ),
            JobRunRecord(
                started_at="2026-06-29 10:05:00",
                finished_at="2026-06-29 10:05:10",
                job_id="sync_universe",
                job_name="同步 A 股列表",
                success=True,
                message="ok",
            ),
            JobRunRecord(
                started_at="2026-06-29 10:02:00",
                finished_at="2026-06-29 10:02:05",
                job_id="prefetch_tushare",
                job_name="预拉 Tushare",
                success=True,
                message="ok",
            ),
        ]
        ordered = order_run_log_records(records)
        self.assertEqual([item.job_id for item in ordered], ["prefetch_tushare", "sync_universe", "collect_quotes"])

    def test_list_run_log_returns_display_order(self) -> None:
        from collections import deque

        from vnpy_ashare.scheduler.manager import JobRunRecord, TaskSchedulerManager

        manager = TaskSchedulerManager()
        manager._run_log = deque(
            [
                JobRunRecord(
                    started_at="2026-06-29 10:00:00",
                    finished_at="2026-06-29 10:00:00",
                    job_id="collect_quotes",
                    job_name="行情采集",
                    success=True,
                    message="执行中…",
                    running=True,
                ),
                JobRunRecord(
                    started_at="2026-06-29 10:05:00",
                    finished_at="2026-06-29 10:05:10",
                    job_id="sync_universe",
                    job_name="同步 A 股列表",
                    success=True,
                    message="ok",
                ),
            ]
        )
        ordered = manager.list_run_log()
        self.assertEqual([item.job_id for item in ordered], ["sync_universe", "collect_quotes"])


if __name__ == "__main__":
    unittest.main()
