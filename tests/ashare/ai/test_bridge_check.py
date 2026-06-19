"""AI access 桥接自检。"""

from __future__ import annotations

import logging
import unittest
from unittest.mock import patch

from vnpy_common.ai.access import missing_ai_bridges, warn_missing_ai_bridges


class AiBridgeCheckTests(unittest.TestCase):
    def test_missing_ai_bridges_empty_when_registered(self) -> None:
        from vnpy_ashare.app.bootstrap import install_shared_bridges

        install_shared_bridges()
        self.assertEqual(missing_ai_bridges(), [])

    def test_warn_missing_ai_bridges_logs_when_unregistered(self) -> None:
        with (
            patch("vnpy_common.ai.access._get_ai_context", None),
            patch(
                "vnpy_common.ai.access._stock_completion_builder",
                None,
            ),
            patch("vnpy_common.ai.access._panel_actions_builder", None),
            patch(
                "vnpy_common.ai.access._market_prompt_builder",
                None,
            ),
            patch("vnpy_common.ai.access._persist_team_report", None),
            patch(
                "vnpy_common.ai.symbol_navigation.get_symbol_navigation",
                return_value=None,
            ),
        ):
            missing = missing_ai_bridges()
            self.assertIn("context_store", missing)
            self.assertIn("symbol_navigation", missing)
            logger = logging.getLogger("test.ai.bridge")
            with self.assertLogs(logger, level="WARNING") as logs:
                warn_missing_ai_bridges(logger)
            self.assertTrue(any("桥接未注册" in msg for msg in logs.output))


if __name__ == "__main__":
    unittest.main()
