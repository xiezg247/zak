"""vnpy_common AI access 桥接注册。"""

from __future__ import annotations

import unittest

from vnpy_ashare.app.bootstrap import install_shared_bridges
from vnpy_common.ai.access import (
    build_market_ai_prompt,
    persist_team_analysis_report,
    team_report_href,
)


class AiAccessBridgeTests(unittest.TestCase):
    def test_market_prompt_bridge(self) -> None:
        install_shared_bridges()
        prompt = build_market_ai_prompt(focus="intraday")
        self.assertIsInstance(prompt, str)

    def test_team_report_href_bridge(self) -> None:
        install_shared_bridges()
        href = team_report_href(42, "600519.SSE")
        self.assertIn("zak://team-report/42", href)
        self.assertIn("600519.SSE", href)

    def test_persist_team_report_skips_incomplete(self) -> None:
        install_shared_bridges()
        row = persist_team_analysis_report("600519", "仅子分析师输出")
        self.assertIsNone(row)


if __name__ == "__main__":
    unittest.main()
