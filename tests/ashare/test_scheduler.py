"""定时任务配置测试。"""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.scheduler.config import SchedulerConfig, load_scheduler_config, save_scheduler_config
from vnpy_ashare.scheduler.manager import TaskSchedulerManager


class TestSchedulerConfig(unittest.TestCase):
    def test_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scheduler.json"
            config = SchedulerConfig()
            config.collect_quotes.enabled = True
            config.collect_quotes.interval_seconds = 30
            config.batch_download.download_start = "2018-01-01"
            save_scheduler_config(config, path)

            loaded = load_scheduler_config(path)
            self.assertTrue(loaded.collect_quotes.enabled)
            self.assertEqual(loaded.collect_quotes.interval_seconds, 30)
            self.assertEqual(loaded.batch_download.download_start, "2018-01-01")

    def test_collect_quotes_reschedules_after_completion(self) -> None:
        manager = TaskSchedulerManager()
        manager._config.collect_quotes.enabled = True
        manager._config.collect_quotes.interval_seconds = 12

        with patch.object(
            manager._jobs["collect_quotes"],
            "runner",
            return_value=JobResult(success=True, message="ok"),
        ):
            manager.start()
            time.sleep(0.2)

            status = manager.get_status("collect_quotes")
            self.assertIsNotNone(status)
            assert status is not None
            self.assertIn("上一轮结束后", status.schedule_text)
            self.assertFalse(status.running)
            self.assertEqual(status.last_message, "ok")

            job = manager._scheduler.get_job("collect_quotes")
            self.assertIsNotNone(job)
            assert job is not None
            self.assertIsNotNone(job.next_run_time)

            manager.shutdown()


if __name__ == "__main__":
    unittest.main()
