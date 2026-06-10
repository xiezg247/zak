"""工具结果规范化测试。"""

from __future__ import annotations

import json
import unittest

from vnpy_llm.tools.result import enrich_tool_result, match_error_hint


class ToolResultTests(unittest.TestCase):
    def test_match_symbol_parse_error(self) -> None:
        hint = match_error_hint("无法解析代码: foo")
        self.assertIn("600519.SSE", hint)

    def test_enrich_adds_hint_and_message(self) -> None:
        raw = json.dumps({"error": "无法解析代码: foo"}, ensure_ascii=False)
        enriched = json.loads(enrich_tool_result(raw))
        self.assertIn("hint", enriched)
        self.assertIn("message", enriched)
        self.assertIn("600519.SSE", enriched["hint"])

    def test_enrich_skips_success_payload(self) -> None:
        raw = json.dumps({"symbol": "600519.SSE", "count": 120}, ensure_ascii=False)
        self.assertEqual(enrich_tool_result(raw), raw)

    def test_enrich_keeps_existing_hint(self) -> None:
        raw = json.dumps(
            {"error": "失败", "hint": "自定义建议", "message": "已有说明"},
            ensure_ascii=False,
        )
        self.assertEqual(enrich_tool_result(raw), raw)


if __name__ == "__main__":
    unittest.main()
