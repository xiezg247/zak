"""问小达 MCP 形态选股测试。"""

from __future__ import annotations

import json
import unittest

from vnpy_ashare.integrations.mcp.pattern_screen import parse_wenda_screen_rows, run_pattern_screen_mcp

_SAMPLE = {
    "meta": {"code": 0, "total": 2},
    "headers": [
        "POS",
        "market",
        "sec_code",
        "sec_name",
        "now_price",
        "chg0#",
        "所属行业",
        "选股名称",
        "老鸭头<br>2026.06.11",
    ],
    "data": [
        ["1", "0", "301086", "鸿富瀚", "157.60", "10.60", "@消费电子@", "【@老鸭头@】", "老鸭头"],
        ["2", "1", "603936", "博敏电子", "23.72", "10.02", "@元器件@", "【@老鸭头@】", "老鸭头"],
    ],
}


class PatternMcpTests(unittest.TestCase):
    def test_parse_wenda_screen_rows(self) -> None:
        rows, total = parse_wenda_screen_rows(json.dumps(_SAMPLE), top_n=10)
        self.assertEqual(total, 2)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["symbol"], "301086")
        self.assertEqual(rows[0]["vt_symbol"], "301086.SZSE")
        self.assertEqual(rows[1]["vt_symbol"], "603936.SSE")
        self.assertEqual(rows[0]["last_price"], 157.60)
        self.assertEqual(rows[0]["change_pct"], 10.60)

    def test_run_pattern_screen_mcp_success(self) -> None:
        def _execute(_tool: str, _args: dict) -> str:
            return json.dumps(_SAMPLE)

        result = run_pattern_screen_mcp(
            "old_duck",
            mcp_execute=_execute,
            tool_names=["mcp_tdx_tdx_wenda_quotes"],
            top_n=5,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.source, "mcp")
        self.assertIn("老鸭头", result.condition)
        self.assertEqual(len(result.rows), 2)

    def test_run_pattern_screen_mcp_unavailable(self) -> None:
        self.assertIsNone(
            run_pattern_screen_mcp(
                "old_duck",
                mcp_execute=None,
                tool_names=["mcp_tdx_tdx_wenda_quotes"],
            )
        )


if __name__ == "__main__":
    unittest.main()
