"""Phase 4 单元测试（无 vnpy 环境可运行部分）。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy_ashare.services import report_sources
from vnpy_llm.tools import audit as tool_audit


class ReportSourcesTests(unittest.TestCase):
    def test_report_fallback_flag(self) -> None:
        with patch.dict("os.environ", {"ANALYSIS_REPORT_FALLBACK": "off"}):
            self.assertFalse(report_sources.report_fallback_enabled())
        with patch.dict("os.environ", {"ANALYSIS_REPORT_FALLBACK": "tushare"}):
            self.assertTrue(report_sources.report_fallback_enabled())

    def test_to_ts_code(self) -> None:
        self.assertEqual(report_sources.to_ts_code("600000", "SSE"), "600000.SH")
        self.assertEqual(report_sources.to_ts_code("000001", "SZSE"), "000001.SZ")


class ToolAuditTests(unittest.TestCase):
    def test_tool_audit_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            with patch("vnpy_llm.tools.audit.get_app_db_path", return_value=db_path):
                tool_audit.log_tool_call(
                    session_id="sess1",
                    tool_name="technical_snapshot",
                    arguments={"symbol": "600000.SSE"},
                    result='{"ok": true}',
                    success=True,
                )
                rows = tool_audit.list_recent_tool_calls(session_id="sess1", limit=5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tool_name"], "technical_snapshot")


if __name__ == "__main__":
    unittest.main()
