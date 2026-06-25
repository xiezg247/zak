"""遗留 SQLite 路径解析测试（import-legacy 默认源）。"""

from __future__ import annotations

import unittest

from vnpy_common.paths import (
    DEFAULT_LEGACY_APP_DB,
    DEFAULT_LEGACY_CHAT_DB,
    VNTRADER_DIR,
    get_app_db_path,
    get_chat_db_path,
    legacy_app_db_path,
    legacy_chat_db_path,
)


class LegacyDbPathsTest(unittest.TestCase):
    def test_default_legacy_paths(self) -> None:
        self.assertEqual(DEFAULT_LEGACY_APP_DB, "zak.db")
        self.assertEqual(DEFAULT_LEGACY_CHAT_DB, "llm_chat.db")
        self.assertEqual(legacy_app_db_path(), VNTRADER_DIR / "zak.db")
        self.assertEqual(legacy_chat_db_path(), VNTRADER_DIR / "llm_chat.db")
        self.assertEqual(get_app_db_path(), legacy_app_db_path())
        self.assertEqual(get_chat_db_path(), legacy_chat_db_path())


if __name__ == "__main__":
    unittest.main()
