"""元数据路径解析测试。"""

from __future__ import annotations

import unittest

from vnpy_common.paths import (
    VNTRADER_DIR,
    get_app_db_path,
    get_chat_db_path,
    meta_db_filenames,
)


class MetaDbPathsTest(unittest.TestCase):
    def test_defaults_when_settings_missing(self) -> None:
        app, chat = meta_db_filenames({})
        self.assertEqual(app, "zak.db")
        self.assertEqual(chat, "llm_chat.db")
        self.assertEqual(get_app_db_path({}), VNTRADER_DIR / "zak.db")
        self.assertEqual(get_chat_db_path({}), VNTRADER_DIR / "llm_chat.db")

    def test_custom_relative_paths(self) -> None:
        settings = {
            "database.meta.app": "custom_app.db",
            "database.meta.chat": "custom_chat.db",
        }
        self.assertEqual(get_app_db_path(settings), VNTRADER_DIR / "custom_app.db")
        self.assertEqual(get_chat_db_path(settings), VNTRADER_DIR / "custom_chat.db")


if __name__ == "__main__":
    unittest.main()
