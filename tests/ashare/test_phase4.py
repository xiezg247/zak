"""Phase 4 单元测试（无 vnpy 环境可运行部分）。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch


def _load_module(name: str, rel_path: str):
    path = Path(__file__).resolve().parents[2] / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_report_fallback_flag():
    mod = _load_module("report_sources_mod", "vnpy_ashare/services/report_sources.py")
    with patch.dict("os.environ", {"ANALYSIS_REPORT_FALLBACK": "off"}):
        assert mod.report_fallback_enabled() is False
    with patch.dict("os.environ", {"ANALYSIS_REPORT_FALLBACK": "tushare"}):
        assert mod.report_fallback_enabled() is True


def test_to_ts_code():
    mod = _load_module("report_sources_mod2", "vnpy_ashare/services/report_sources.py")
    assert mod.to_ts_code("600000", "SSE") == "600000.SH"
    assert mod.to_ts_code("000001", "SZSE") == "000001.SZ"


def test_tool_audit_roundtrip(tmp_path, monkeypatch):
    audit_mod = _load_module("tool_audit_mod", "vnpy_llm/tool_audit.py")
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(audit_mod, "APP_DB_PATH", db_path)

    audit_mod.log_tool_call(
        session_id="sess1",
        tool_name="technical_snapshot",
        arguments={"symbol": "600000.SSE"},
        result='{"ok": true}',
        success=True,
    )
    rows = audit_mod.list_recent_tool_calls(session_id="sess1", limit=5)
    assert len(rows) == 1
    assert rows[0]["tool_name"] == "technical_snapshot"
