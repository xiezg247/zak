"""定时任务配置测试。"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.scheduler.config import SchedulerConfig, load_scheduler_config, save_scheduler_config
from vnpy_ashare.scheduler.manager import TaskSchedulerManager


class TestSchedulerConfig(unittest.TestCase):
    def test_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scheduler.json"
            config = SchedulerConfig()
            config.collect_quotes.enabled = True
            config.collect_quotes.interval_seconds = 30
            config.batch_download_universe.download_start = "2018-01-01"
            save_scheduler_config(config, path)

            loaded = load_scheduler_config(path)
            self.assertTrue(loaded.collect_quotes.enabled)
            self.assertEqual(loaded.collect_quotes.interval_seconds, 30)
            self.assertEqual(loaded.batch_download_universe.download_start, "2018-01-01")

    def test_auto_screen_config_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scheduler.json"
            config = SchedulerConfig()
            config.screen_intraday.enabled = True
            config.screen_intraday.recipe_id = "intraday_multi"
            config.screen_post_close.top_n = 15
            save_scheduler_config(config, path)

            loaded = load_scheduler_config(path)
            self.assertTrue(loaded.screen_intraday.enabled)
            self.assertEqual(loaded.screen_intraday.recipe_id, "intraday_multi")
            self.assertEqual(loaded.screen_post_close.top_n, 15)

    def test_screen_intraday_cron_trigger_accepts_multi_hours(self) -> None:
        from apscheduler.triggers.cron import CronTrigger

        from vnpy_ashare.scheduler.manager import _normalize_cron_hours

        hours = _normalize_cron_hours("10, 14")
        trigger = CronTrigger(day_of_week="mon-fri", hour=hours, minute=0)
        self.assertEqual(hours, "10,14")
        self.assertIsNotNone(trigger)

    def test_screen_jobs_listed(self) -> None:
        manager = TaskSchedulerManager()
        job_ids = {item.job_id for item in manager.list_status()}
        self.assertIn("screen_intraday", job_ids)
        self.assertIn("screen_post_close", job_ids)

    def test_new_tushare_jobs_listed(self) -> None:
        manager = TaskSchedulerManager()
        job_ids = {item.job_id for item in manager.list_status()}
        self.assertIn("sync_trade_calendar", job_ids)
        self.assertIn("sync_stock_industry", job_ids)
        self.assertIn("prefetch_moneyflow", job_ids)
        self.assertIn("batch_download_universe", job_ids)
        self.assertIn("batch_fill_stale", job_ids)
        self.assertIn("prefetch_concept_board", job_ids)
        self.assertIn("warm_market_summary", job_ids)
        self.assertIn("warm_watchlist_strategy_cache", job_ids)
        self.assertNotIn("batch_download", job_ids)

    def test_new_job_config_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scheduler.json"
            config = SchedulerConfig()
            config.sync_trade_calendar.enabled = True
            config.sync_trade_calendar.cron_hour = 7
            config.sync_trade_calendar.cron_minute = 45
            config.sync_stock_industry.enabled = True
            config.sync_stock_industry.cron_hour = 8
            config.sync_stock_industry.cron_minute = 15
            config.batch_fill_stale.enabled = True
            config.batch_fill_stale.cron_hour = 17
            config.batch_fill_stale.cron_minute = 5
            save_scheduler_config(config, path)

            loaded = load_scheduler_config(path)
            self.assertTrue(loaded.sync_trade_calendar.enabled)
            self.assertEqual(loaded.sync_trade_calendar.cron_minute, 45)
            self.assertTrue(loaded.sync_stock_industry.enabled)
            self.assertEqual(loaded.sync_stock_industry.cron_minute, 15)
            self.assertTrue(loaded.batch_fill_stale.enabled)
            self.assertEqual(loaded.batch_fill_stale.cron_hour, 17)

    def test_batch_download_has_buffer_before_next_job(self) -> None:
        config = SchedulerConfig()
        download_end = config.batch_download_universe.cron_hour * 60 + config.batch_download_universe.cron_minute + 30
        next_job = config.prefetch_moneyflow.cron_hour * 60 + config.prefetch_moneyflow.cron_minute
        self.assertGreaterEqual(next_job - download_end, 10)

    def test_custom_cron_preserved_on_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scheduler.json"
            config = SchedulerConfig()
            config.prefetch_moneyflow.cron_hour = 16
            config.prefetch_moneyflow.cron_minute = 28
            save_scheduler_config(config, path)

            loaded = load_scheduler_config(path)
            self.assertEqual(loaded.prefetch_moneyflow.cron_minute, 28)

    def test_post_close_defaults_are_spaced(self) -> None:
        config = SchedulerConfig()
        minutes = [
            config.batch_download_universe.cron_hour * 60 + config.batch_download_universe.cron_minute,
            config.prefetch_moneyflow.cron_hour * 60 + config.prefetch_moneyflow.cron_minute,
            config.prefetch_tushare.cron_hour * 60 + config.prefetch_tushare.cron_minute,
            config.sync_suspend_daily.cron_hour * 60 + config.sync_suspend_daily.cron_minute,
            config.prefetch_concept_board.cron_hour * 60 + config.prefetch_concept_board.cron_minute,
            config.warm_market_summary.cron_hour * 60 + config.warm_market_summary.cron_minute,
            config.screen_post_close.cron_hour * 60 + config.screen_post_close.cron_minute,
            config.scan_horizon_outlook.cron_hour * 60 + config.scan_horizon_outlook.cron_minute,
            config.batch_fill_stale.cron_hour * 60 + config.batch_fill_stale.cron_minute,
            config.warm_watchlist_strategy_cache.cron_hour * 60 + config.warm_watchlist_strategy_cache.cron_minute,
            config.fill_focus_pool_minute.cron_hour * 60 + config.fill_focus_pool_minute.cron_minute,
        ]
        for earlier, later in zip(minutes, minutes[1:], strict=False):
            self.assertGreaterEqual(later - earlier, 5)

    def test_screen_intraday_skips_off_hours(self) -> None:
        manager = TaskSchedulerManager()
        next_run = datetime(2026, 6, 10, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
        with patch(
            "vnpy_ashare.jobs.runners.run_scheduled_auto_screen",
            return_value=JobResult(success=True, skipped=True, message="非交易时段，已跳过"),
        ):
            manager._wrap_job("screen_intraday", force=False)

        records = manager.list_run_log(limit=1)
        self.assertEqual(records[0].job_name, "盘中自动选股")
        self.assertTrue(records[0].skipped)

    def test_collect_quotes_reschedules_after_completion(self) -> None:
        manager = TaskSchedulerManager()
        manager._config.collect_quotes.enabled = True
        manager._config.collect_quotes.interval_seconds = 12
        manager.start()

        with patch(
            "vnpy_ashare.scheduler.manager.is_ashare_trading_session",
            return_value=True,
        ):
            with patch(
                "vnpy_ashare.jobs.runners.run_collect_quotes",
                return_value=JobResult(success=True, message="ok"),
            ) as mock_run:
                manager._wrap_job("collect_quotes", force=False)
                mock_run.assert_called_once()

        status = manager.get_status("collect_quotes")
        self.assertIsNotNone(status)
        assert status is not None
        self.assertIn("ok", status.last_message or "")

        job = manager._scheduler.get_job("collect_quotes")
        self.assertIsNotNone(job)
        assert job is not None
        self.assertIsNotNone(job.next_run_time)

        manager.shutdown()

    def test_collect_quotes_skips_off_hours(self) -> None:
        manager = TaskSchedulerManager()
        next_run = datetime(2026, 6, 10, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
        with patch(
            "vnpy_ashare.jobs.runners.is_ashare_trading_session",
            return_value=False,
        ):
            with patch(
                "vnpy_ashare.jobs.runners.next_quotes_collect_at",
                return_value=next_run,
            ):
                manager._wrap_job("collect_quotes", force=False)

        records = manager.list_run_log(limit=1)
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0].skipped)
        self.assertIn("非交易时段", records[0].message)

        status = manager.get_status("collect_quotes")
        assert status is not None
        self.assertIsNone(status.last_success)

    def test_run_log_records_completed_jobs(self) -> None:
        manager = TaskSchedulerManager()

        with patch(
            "vnpy_ashare.scheduler.manager.run_job",
            return_value=JobResult(success=True, message="synced 100"),
        ):
            manager._wrap_job("sync_universe")

        records = manager.list_run_log(limit=10)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].job_name, "同步 A 股列表")
        self.assertTrue(records[0].success)
        self.assertEqual(records[0].message, "synced 100")

    def test_run_log_keeps_recent_entries_only(self) -> None:
        from collections import deque

        manager = TaskSchedulerManager()
        manager._run_log = deque(maxlen=3)

        with patch(
            "vnpy_ashare.scheduler.manager.run_job",
            return_value=JobResult(success=True, message="ok"),
        ):
            for _ in range(5):
                manager._wrap_job("sync_universe")

        self.assertEqual(len(manager.list_run_log()), 3)


if __name__ == "__main__":
    unittest.main()
