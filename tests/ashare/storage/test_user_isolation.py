"""多用户隔离测试（PostgreSQL）。"""

from __future__ import annotations

import os
import unittest
import uuid

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.auth.users import create_user
from vnpy_ashare.storage.connection import connect
from vnpy_ashare.storage.repositories import watchlist as watchlist_repo
from vnpy_common.auth.context import set_current_user
from vnpy_common.storage.config import force_database_url, reset_storage_config


class TestUserIsolation(unittest.TestCase):
    def setUp(self) -> None:
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            self.skipTest("需要 DATABASE_URL")
        reset_storage_config()
        force_database_url(url)
        suffix = uuid.uuid4().hex[:8]
        with connect() as conn:
            self.user_a = create_user(conn, username=f"alice_{suffix}", password="pass-a", display_name="Alice")
            self.user_b = create_user(conn, username=f"bob_{suffix}", password="pass-b", display_name="Bob")

    def tearDown(self) -> None:
        from vnpy_ashare.storage.auth import users as users_module

        users_module._cached_default_user_id = None
        users_module._cached_default_user_db = None
        reset_storage_config()

    def test_watchlist_isolated_by_user(self) -> None:
        set_current_user(self.user_a.id)
        symbol = str(600000 + uuid.uuid4().int % 3999)
        self.assertTrue(watchlist_repo.add_watchlist_item(symbol, Exchange.SSE, "测试"))

        set_current_user(self.user_b.id)
        self.assertEqual(watchlist_repo.watchlist_item_count(), 0)

        set_current_user(self.user_a.id)
        self.assertEqual(watchlist_repo.watchlist_item_count(), 1)
