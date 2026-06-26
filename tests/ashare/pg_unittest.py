"""PostgreSQL unittest 辅助（替代已移除的 connection._db_path mock）。"""

from __future__ import annotations

import os
import unittest
import uuid

from vnpy_ashare.storage.auth.users import create_user, get_or_create_default_user_id
from vnpy_ashare.storage.connection import connect
from vnpy_common.auth.context import clear_current_user, set_current_user
from vnpy_common.storage.config import force_database_url, reset_storage_config


def require_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise unittest.SkipTest("需要 DATABASE_URL")
    return url


def reset_auth_user_cache() -> None:
    try:
        from vnpy_ashare.storage.auth import users as users_module

        users_module._cached_default_user_id = None
        users_module._cached_default_user_db = None
    except ImportError:
        pass


class PgStorageTestCase(unittest.TestCase):
    """用户域存储测试：默认每用例独立 user，避免共享 PostgreSQL 互相污染。"""

    isolated_user: bool = True

    def setUp(self) -> None:
        url = require_database_url()
        reset_storage_config()
        force_database_url(url)
        if self.isolated_user:
            suffix = uuid.uuid4().hex[:8]
            with connect() as conn:
                user = create_user(
                    conn,
                    username=f"ut_{suffix}",
                    password="test",
                    display_name=f"test-{suffix}",
                )
            set_current_user(user.id)
            self.test_user_id = user.id
        else:
            user_id = get_or_create_default_user_id()
            set_current_user(user_id)
            self.test_user_id = user_id

    def tearDown(self) -> None:
        clear_current_user()
        reset_storage_config()
        reset_auth_user_cache()


class PgAppStorageTestCase(unittest.TestCase):
    """全局 app 表测试（universe、sector_flow、financial 等）。"""

    def setUp(self) -> None:
        url = require_database_url()
        reset_storage_config()
        force_database_url(url)

    def tearDown(self) -> None:
        reset_storage_config()
        reset_auth_user_cache()
