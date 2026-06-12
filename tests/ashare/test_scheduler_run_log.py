"""调度器执行日志（过程输出）测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.jobs.progress import bind_job_log, job_log, job_progress
from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.scheduler.manager import JobRunRecord, TaskSchedulerManager
from vnpy_common.ui.theme.build_extra import format_scheduler_run_log_html
from vnpy_common.ui.theme.tokens import LIGHT_TOKENS


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
    def test_running_record_renders_detail_lines(self) -> None:
        record = JobRunRecord(
            job_id="batch_download_universe",
            job_name="全市场日 K",
            started_at="2026-06-12 16:25:00",
            finished_at="2026-06-12 16:25:00",
            success=True,
            skipped=False,
            message="执行中…",
            running=True,
            detail_lines=["[开始] 全市场日 K", "待下载 3 只", "✓ 600519.SSE"],
        )
        html = format_scheduler_run_log_html(LIGHT_TOKENS, [record])
        self.assertIn("运行中", html)
        self.assertIn("600519.SSE", html)
        self.assertIn(LIGHT_TOKENS.accent, html)

    def test_wrap_job_emits_progress_lines(self) -> None:
        manager = TaskSchedulerManager()

        def runner() -> JobResult:
            job_log("step-1")
            job_log("step-2")
            return JobResult(success=True, message="done")

        meta = manager._jobs["sync_universe"]
        original = meta.runner
        meta.runner = runner
        try:
            manager._wrap_job("sync_universe")
        finally:
            meta.runner = original

        records = manager.list_run_log(limit=1)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertFalse(record.running)
        self.assertIn("step-1", record.detail_lines)
        self.assertIn("step-2", record.detail_lines)
        self.assertIn("[结束] 成功", record.detail_lines[-1])


if __name__ == "__main__":
    unittest.main()
