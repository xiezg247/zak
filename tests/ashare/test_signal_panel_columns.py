"""信号区列配置测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.config.preferences.signal_panel_columns import (
    DEFAULT_VISIBLE_OPTIONAL_KEYS,
    SIGNAL_PANEL_OPTIONAL_COLUMNS,
    normalize_visible_optional_keys,
)


class SignalPanelColumnsTests(unittest.TestCase):
    def test_continuation_columns_default_hidden(self) -> None:
        keys = set(DEFAULT_VISIBLE_OPTIONAL_KEYS)
        self.assertNotIn("continuation_pattern", keys)
        self.assertNotIn("outlook_compact", keys)

    def test_continuation_columns_available_in_menu(self) -> None:
        optional = {key for key, _ in SIGNAL_PANEL_OPTIONAL_COLUMNS}
        self.assertIn("continuation_pattern", optional)
        self.assertIn("outlook_compact", optional)

    def test_normalize_keeps_continuation_when_requested(self) -> None:
        keys = normalize_visible_optional_keys(["signal", "continuation_pattern", "outlook_compact"])
        self.assertEqual(keys[-2:], ["continuation_pattern", "outlook_compact"])


if __name__ == "__main__":
    unittest.main()
