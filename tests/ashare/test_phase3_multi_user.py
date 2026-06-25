"""Phase 3：Scheduler 选主与用户偏好测试。"""

from __future__ import annotations

import os
import unittest
import uuid
from unittest.mock import patch

from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.scheduler.leader import is_user_scoped_job, should_run_scheduler
from vnpy_ashare.scheduler.manager import TaskSchedulerManager
from vnpy_ashare.screener.hard_filter_prefs import (
    HardFilterPrefs,
    load_hard_filter_prefs,
    save_hard_filter_prefs,
)
from vnpy_ashare.storage.auth.preferences import get_pref, set_pref
from vnpy_ashare.storage.auth.users import create_user
from vnpy_ashare.storage.connection import connect, init_app_db
from vnpy_common.auth.context import clear_current_user, set_current_user
from vnpy_common.storage.config import reset_storage_config


class TestSchedulerLeader(unittest.TestCase):
    def test_should_run_scheduler_respects_env(self) -> None:
        with patch.dict(os.environ, {"ZAK_RUN_SCHEDULER": "true"}, clear=False):
            self.assertTrue(should_run_scheduler())
        with patch.dict(os.environ, {"ZAK_RUN_SCHEDULER": "false"}, clear=False):
            self.assertFalse(should_run_scheduler())
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(should_run_scheduler())

    def test_start_skipped_when_not_leader(self) -> None:
        with patch.dict(os.environ, {"ZAK_RUN_SCHEDULER": "false"}, clear=False):
            manager = TaskSchedulerManager()
            manager.start()
            self.assertFalse(manager._scheduler.running)

    def test_user_scoped_jobs(self) -> None:
        self.assertTrue(is_user_scoped_job("sync_bilibili_feed"))
        self.assertTrue(is_user_scoped_job("screen_intraday"))
        self.assertFalse(is_user_scoped_job("sync_universe"))

    def test_user_scoped_job_runs_per_active_user(self) -> None:
        manager = TaskSchedulerManager()
        calls: list[str] = []

        def fake_run_job(job_id: str, *, force: bool = False, engine=None) -> JobResult:
            from vnpy_ashare.storage.auth.scope import get_user_id

            calls.append(get_user_id())
            return JobResult(success=True, message=f"ok-{job_id}")

        with patch("vnpy_ashare.scheduler.manager.run_job", side_effect=fake_run_job):
            with patch(
                "vnpy_ashare.storage.auth.users.list_active_users",
                return_value=[
                    type("U", (), {"id": "u1", "username": "alice"})(),
                    type("U", (), {"id": "u2", "username": "bob"})(),
                ],
            ):
                manager._wrap_job("sync_bilibili_feed", force=True)

        self.assertEqual(calls, ["u1", "u2"])


class TestUserPreferencesIsolation(unittest.TestCase):
    def setUp(self) -> None:
        import os

        from vnpy_common.storage.config import force_database_url, reset_storage_config

        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            self.skipTest("需要 DATABASE_URL")
        reset_storage_config()
        force_database_url(url)
        init_app_db()
        suffix = uuid.uuid4().hex[:8]
        with connect() as conn:
            alice = create_user(conn, username=f"alice_{suffix}", password="secret")
            bob = create_user(conn, username=f"bob_{suffix}", password="secret")
        self.alice_id = alice.id
        self.bob_id = bob.id

    def tearDown(self) -> None:
        clear_current_user()
        reset_storage_config()

    def test_prefs_isolated_between_users(self) -> None:
        prefs_a = HardFilterPrefs(
            exclude_st=True,
            exclude_suspended=True,
            min_amount_wan=8000.0,
            min_total_mv_yi=50.0,
            exclude_new_listing=False,
            min_listing_days=60,
            exclude_limit_board=False,
        )
        prefs_b = HardFilterPrefs(
            exclude_st=True,
            exclude_suspended=True,
            min_amount_wan=3000.0,
            min_total_mv_yi=20.0,
            exclude_new_listing=True,
            min_listing_days=90,
            exclude_limit_board=True,
        )

        set_current_user(self.alice_id)
        save_hard_filter_prefs(prefs_a)
        set_current_user(self.bob_id)
        save_hard_filter_prefs(prefs_b)

        set_current_user(self.alice_id)
        loaded_a = load_hard_filter_prefs()
        set_current_user(self.bob_id)
        loaded_b = load_hard_filter_prefs()

        self.assertEqual(loaded_a.min_amount_wan, 8000.0)
        self.assertEqual(loaded_b.min_amount_wan, 3000.0)
        self.assertTrue(loaded_b.exclude_new_listing)

    def test_set_get_pref_roundtrip(self) -> None:
        set_current_user(self.alice_id)
        set_pref("trading", "risk_capital", {"amount": 100000})
        self.assertEqual(get_pref("trading", "risk_capital"), {"amount": 100000})


if __name__ == "__main__":
    unittest.main()
