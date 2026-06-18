"""LLM 会话存储测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import vnpy_llm.chat.store as store


class TestChatStore(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch.object(store, "_chat_db_path", return_value=self.db_path)
        self._patcher.start()
        self.chat_store = store.ChatStore()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_append_and_list_messages(self) -> None:
        session_id = self.chat_store.create_session(title="测试")
        self.chat_store.append_message(session_id, role="user", content="你好")
        self.chat_store.append_message(session_id, role="assistant", content="你好，有什么可以帮你？")

        messages = self.chat_store.list_messages(session_id)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].role, "user")
        self.assertEqual(messages[1].content, "你好，有什么可以帮你？")

    def test_clear_messages(self) -> None:
        session_id = self.chat_store.get_or_create_default_session()
        self.chat_store.append_message(session_id, role="user", content="test")
        self.chat_store.clear_messages(session_id)
        self.assertEqual(self.chat_store.list_messages(session_id), [])


if __name__ == "__main__":
    unittest.main()
