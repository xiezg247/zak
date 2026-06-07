"""定时任务配置测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vnpy_ashare.scheduler.config import SchedulerConfig, load_scheduler_config, save_scheduler_config


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


if __name__ == "__main__":
    unittest.main()
