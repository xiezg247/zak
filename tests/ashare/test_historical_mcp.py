"""historical_mcp 单元测试。"""

from __future__ import annotations

import json
import unittest

from vnpy_ashare.services.analysis_detail.historical_mcp import (
    _extract_return_pct,
    fetch_historical_pattern_mcp,
    local_historical_sufficient,
)
from vnpy_ashare.services.analysis_detail.mcp_binding import McpBinding


def _wenda_payload(**extra_fields: str) -> str:
    headers = ["sec_code", "sec_name", "now_price", "chg", *extra_fields.keys()]
    row = ["600000", "浦发银行", "10.50", "1.20", *extra_fields.values()]
    return json.dumps({"headers": headers, "data": [row]}, ensure_ascii=False)


class HistoricalMcpTests(unittest.TestCase):
    def test_local_historical_sufficient(self) -> None:
        self.assertTrue(local_historical_sufficient({"return_pct": 3.5}))
        self.assertTrue(
            local_historical_sufficient(
                {"data_quality": "mcp_fallback", "mcp_fields": {"20日涨跌幅": "3.5"}},
            ),
        )
        self.assertFalse(local_historical_sufficient({"warnings": ["无数据"]}))

    def test_extract_return_pct_prefers_matching_lookback(self) -> None:
        fields = {"5日涨跌幅": "1.2", "20日涨跌幅": "8.6", "60日涨跌幅": "-2.1"}
        self.assertEqual(_extract_return_pct(fields, 20), 8.6)
        self.assertEqual(_extract_return_pct(fields, 5), 1.2)

    def test_fetch_historical_pattern_mcp(self) -> None:
        def _execute(name: str, args: dict) -> str:
            return _wenda_payload(**{"20日涨跌幅": "6.80", "振幅": "12.5", "MACD.MACD": "-0.12"})

        mcp = McpBinding(execute=_execute, tool_names=["mcp_tdx_tdx_wenda_quotes"])
        result = fetch_historical_pattern_mcp("600000.SSE", lookback=20, mcp=mcp)
        self.assertEqual(result["data_quality"], "mcp_fallback")
        self.assertEqual(result["return_pct"], 6.8)
        self.assertEqual(result["sources"], ["tdx_mcp"])
        self.assertIn("mcp_fields", result)

    def test_fetch_without_mcp(self) -> None:
        result = fetch_historical_pattern_mcp("600000.SSE", lookback=20, mcp=McpBinding())
        self.assertFalse(local_historical_sufficient(result))
        self.assertIn("MCP 未连接", result["warnings"][0])


if __name__ == "__main__":
    unittest.main()
