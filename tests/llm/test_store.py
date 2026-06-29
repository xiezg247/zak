"""LLM 会话存储测试。"""

from __future__ import annotations

import os
import unittest
import uuid

import vnpy_llm.chat.store as store
from vnpy_ashare.storage.auth.users import get_or_create_default_user_id
from vnpy_common.auth.context import clear_current_user, set_current_user
from vnpy_common.storage.config import force_database_url, reset_storage_config


class TestChatRepository(unittest.TestCase):
    def setUp(self) -> None:
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            self.skipTest("需要 DATABASE_URL")
        reset_storage_config()
        force_database_url(url)
        set_current_user(get_or_create_default_user_id())
        self.chat_store = store.ChatRepository()

    def tearDown(self) -> None:
        clear_current_user()
        reset_storage_config()

    def test_append_and_list_messages(self) -> None:
        session_id = self.chat_store.create_session(title=f"测试-{uuid.uuid4().hex[:6]}")
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
