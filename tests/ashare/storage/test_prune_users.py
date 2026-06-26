"""prune_to_default_user 集成测试（PostgreSQL）。"""

from __future__ import annotations

import unittest
import uuid

import pytest

from vnpy_ashare.storage.auth.prune_users import prune_to_default_user
from vnpy_ashare.storage.auth.users import create_user, list_users
from vnpy_common.auth.users import DEFAULT_USERNAME


@pytest.mark.usefixtures("pg_storage")
class PruneUsersTests(unittest.TestCase):
    def test_prune_removes_non_default_users(self) -> None:
        suffix = uuid.uuid4().hex[:8]
        username = f"bob_{suffix}"
        create_user(username=username, password="secret", display_name="Bob")

        report = prune_to_default_user()

        self.assertIn(username, report.removed_usernames)
        users = list_users()
        self.assertEqual([user.username for user in users], [DEFAULT_USERNAME])


if __name__ == "__main__":
    unittest.main()
