"""LLM 工具调用审计日志测试。"""

from __future__ import annotations

import os
import unittest

import vnpy_llm.tools.audit as tool_audit
from vnpy_ashare.storage.auth.users import get_or_create_default_user_id
from vnpy_common.auth.context import clear_current_user, set_current_user
from vnpy_common.storage.config import force_database_url, reset_storage_config


class ToolAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            self.skipTest("需要 DATABASE_URL")
        reset_storage_config()
        force_database_url(url)
        set_current_user(get_or_create_default_user_id())

    def tearDown(self) -> None:
        clear_current_user()
        reset_storage_config()

    def test_tool_audit_roundtrip(self) -> None:
        tool_audit.log_tool_call(
            session_id="sess1",
            tool_name="technical_snapshot",
            arguments={"symbol": "600000.SSE"},
            result='{"ok": true}',
            success=True,
        )
        rows = tool_audit.list_recent_tool_calls(session_id="sess1", limit=5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tool_name"], "technical_snapshot")


if __name__ == "__main__":
    unittest.main()
