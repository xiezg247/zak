"""定时任务上次执行 meta 持久化测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.scheduler.job_meta import clear_job_run_meta, load_job_run_meta, save_job_run_meta
from vnpy_ashare.scheduler.manager import TaskSchedulerManager
from vnpy_ashare.storage.connection import init_app_db


class SchedulerJobMetaTests(unittest.TestCase):
    def setUp(self) -> None:
        init_app_db()
        clear_job_run_meta("sync_universe")

    def tearDown(self) -> None:
        clear_job_run_meta("sync_universe")

    def test_save_and_load_roundtrip(self) -> None:
        save_job_run_meta(
            "sync_universe",
            last_run_at="2026-06-12 16:33:00",
            last_message="已同步停牌记录 12 条",
            last_success=True,
        )
        loaded = load_job_run_meta("sync_universe")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.last_run_at, "2026-06-12 16:33:00")
        self.assertEqual(loaded.last_message, "已同步停牌记录 12 条")
        self.assertTrue(loaded.last_success)

    def test_manager_restores_last_run_after_reload(self) -> None:
        save_job_run_meta(
            "sync_universe",
            last_run_at="2026-06-12 16:33:00",
            last_message="done",
            last_success=True,
        )
        manager = TaskSchedulerManager()
        status = next(item for item in manager.list_status() if item.job_id == "sync_universe")
        self.assertEqual(status.last_run_at, "2026-06-12 16:33:00")
        self.assertEqual(status.last_message, "done")
        self.assertTrue(status.last_success)

    def test_wrap_job_persists_last_run(self) -> None:
        manager = TaskSchedulerManager()

        def runner() -> JobResult:
            return JobResult(success=True, message="persist-me")

        meta = manager._jobs["sync_universe"]
        original = meta.runner
        meta.runner = runner
        try:
            manager._wrap_job("sync_universe")
        finally:
            meta.runner = original

        loaded = load_job_run_meta("sync_universe")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.last_message, "persist-me")
        self.assertTrue(loaded.last_success)


if __name__ == "__main__":
    unittest.main()
